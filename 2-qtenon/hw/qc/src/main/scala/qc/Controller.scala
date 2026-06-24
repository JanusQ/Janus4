package qc

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}

import chisel3._
import chisel3.util._
import chisel3.util.HasBlackBoxResource
import chisel3.experimental.IntParam
import freechips.rocketchip.rocket._
import freechips.rocketchip.tilelink._
import freechips.rocketchip.util.InOrderArbiter
import org.chipsalliance.cde.config._
import freechips.rocketchip.diplomacy._
import freechips.rocketchip.tile._
import freechips.rocketchip.util.ClockGate
import freechips.rocketchip.tilelink.TLIdentityNode
import freechips.rocketchip.rocket.constants.MemoryOpConstants

import QunatumControllerISA._
import IndexTableWriteType._

class QuantumController(qubit_number: Int)(implicit p: Parameters)
    extends LazyRoCC (
        opcodes = OpcodeSet.custom0
    ) {
    override lazy val module = new QuantumControllerModule(this)(p, qubit_number = qubit_number)

    val mem_read = LazyModule(new MemReadCore)

    // TEMP: determine how the node is connected
    override val tlNode = mem_read.node
}

class QuantumControllerModule(outer: QuantumController)(implicit p: Parameters, qubit_number: Int) extends LazyRoCCModuleImp(outer)
    with HasCoreParameters with MemoryOpConstants {
        import outer.mem_read

        // add module
        val index_table = Module(new IndexTable(qubit_number))

        // state machine
        val s_idle :: s_mem_req :: s_mem_wait :: s_acquire_wait :: s_acquire_req :: s_resp :: Nil = Enum(6)
        val state = RegInit(s_idle)

        // register
        val resp_rd = RegInit(0.U.asTypeOf(io.resp.bits.rd))
        val resp_data = RegInit(0.U(64.W))
        val funct = RegInit(0.U.asTypeOf(io.cmd.bits.inst.funct))
        val rs1 = RegInit(0.U.asTypeOf(io.cmd.bits.rs1))
        val rs2 = RegInit(0.U.asTypeOf(io.cmd.bits.rs2))

        val classic_addr = RegInit(0.U(39.W))
        val quantum_addr = RegInit(0.U(39.W))
        val length = RegInit(0.U(25.W))
        val acquireStoreAddrWidth = io.mem.req.bits.addr.getWidth
        val mem_dprv = RegInit(0.U.asTypeOf(io.mem.req.bits.dprv))
        val mem_dv = RegInit(false.B)
        val acquire_store_addr = RegInit(0.U(acquireStoreAddrWidth.W))

        // Tutorial-visible paper-aligned backend state.
        // The full paper evaluates physical quantum timing separately, but this
        // miniature backend keeps the ISA-visible ordering honest: q_gen has a
        // PGU delay, q_run has shot-dependent completion, and q_acquire only
        // returns completed measurements.
        val tutorialParamBase = "h0040".U(20.W)
        val pguLatencyCountdownStart = 999.U(16.W) // 1000 PGU cycles, counted down from 999 to 0.
        val tutorialParamWords = RegInit(VecInit(Seq.fill(4)(0.U(16.W))))
        val genParamWords = RegInit(VecInit(Seq.fill(4)(0.U(16.W))))
        val preparedParamWords = RegInit(VecInit(Seq.fill(4)(0.U(16.W))))
        val runParamWords = RegInit(VecInit(Seq.fill(4)(0.U(16.W))))
        val preparedValid = RegInit(false.B)
        val genBusy = RegInit(false.B)
        val genCounter = RegInit(0.U(16.W))
        val runBusy = RegInit(false.B)
        val runQueued = RegInit(false.B)
        val runCounter = RegInit(0.U(16.W))
        val runShots = RegInit(0.U(16.W))
        val queuedRunShots = RegInit(0.U(16.W))
        val genEpoch = RegInit(0.U(8.W))
        val runEpoch = RegInit(0.U(8.W))
        val perfCounter = RegInit(0.U(64.W))
        val completedRunShots = RegInit(0.U(32.W))
        val measureWord = RegInit(0.U(64.W))
        val measureValid = RegInit(false.B)
        val acquireResponseOnly = RegInit(false.B)
        val fullStoreMask = Fill(xLen / 8, 1.U(1.W))

        // the length is based on qubit_number
        val is_index_table = outer.mem_read.module.io.output.bits.quantum_addr >= 0.U &&
                             outer.mem_read.module.io.output.bits.quantum_addr < 0x07fffffff.U
        val q_update_direct_valid = io.cmd.fire && (io.cmd.bits.inst.funct === Q_UPDATE_CMD)
        val mem_read_write_valid = outer.mem_read.module.io.output.valid && is_index_table
        val write_valid = mem_read_write_valid || q_update_direct_valid
        val write_addr = Mux(
            q_update_direct_valid,
            io.cmd.bits.rs2(19, 0),
            outer.mem_read.module.io.output.bits.quantum_addr(19, 0),
        )
        val write_length = Mux(q_update_direct_valid, 4.U, outer.mem_read.module.io.output.bits.length)
        val write_data = Mux(
            q_update_direct_valid,
            Cat(0.U(64.W), io.cmd.bits.rs1),
            outer.mem_read.module.io.output.bits.data,
        )
        val touchedParamWindow = WireDefault(false.B)

        val runTheta0 = runParamWords(0)
        val runTheta1 = runParamWords(1)
        val runIter = runParamWords(2)
        val runScoreWide = Wire(UInt(21.W))
        val runObjectivePpm = Wire(UInt(20.W))
        val runSampleMix = Wire(UInt(8.W))
        val runSampleBits = Wire(UInt(2.W))
        runScoreWide := (runTheta0 * 37.U) + (runTheta1 * 19.U) +
                        (runIter * 53.U) + runShots + genEpoch + runEpoch
        runObjectivePpm := Mux(runScoreWide(19, 0) >= 1000000.U, runScoreWide(19, 0) - 1000000.U, runScoreWide(19, 0))
        runSampleMix := runObjectivePpm(7, 0) ^ runTheta0(7, 0) ^ runTheta1(7, 0) ^
                        runIter(7, 0) ^ runShots(7, 0)
        runSampleBits := runSampleMix(1, 0)

        val measurementPending = runBusy || runQueued

        // CONNECTION for the accelerator
        // TODO: add more delicite control
        // TODO: the ready signal for io.cmd.ready
        io.cmd.ready := (state === s_idle)
        io.busy := (state =/= s_idle)
        io.resp.valid := (state === s_resp)
        io.resp.bits.rd := resp_rd
        io.resp.bits.data := resp_data
        perfCounter := perfCounter + 1.U

        // TODO: using gated clock to save energy

        // Issue commands
        when(io.cmd.fire){
            resp_rd := io.cmd.bits.inst.rd
            funct := io.cmd.bits.inst.funct
            rs1 := io.cmd.bits.rs1
            rs2 := io.cmd.bits.rs2
            resp_data := 0.U

            // decode the command
            classic_addr := io.cmd.bits.rs1(38, 0)
            quantum_addr := io.cmd.bits.rs2(38, 0)
            length := io.cmd.bits.rs2(63, 39)
            mem_dprv := io.cmd.bits.status.dprv
            mem_dv := io.cmd.bits.status.dv
            state := s_idle

            switch(io.cmd.bits.inst.funct) {
                is(Q_SET_CMD) { state := s_mem_req }
                is(Q_ACQUIRE_CMD) {
                    acquire_store_addr := io.cmd.bits.rs1(acquireStoreAddrWidth - 1, 0)
                    acquireResponseOnly := io.cmd.bits.rs1 === 0.U
                    when(measureValid) {
                        resp_data := measureWord
                        state := Mux(io.cmd.bits.rs1 === 0.U, s_resp, s_acquire_req)
                    }.elsewhen(measurementPending) {
                        resp_data := 0.U
                        state := s_acquire_wait
                    }.otherwise {
                        resp_data := 0.U
                        state := Mux(io.cmd.bits.rs1 === 0.U, s_resp, s_acquire_req)
                    }
                }
                is(Q_UPDATE_CMD) {
                    state := s_idle
                }
                is(Q_GEN_CMD) {
                    for (i <- 0 until 4) {
                        genParamWords(i) := tutorialParamWords(i)
                    }
                    genBusy := true.B
                    genCounter := pguLatencyCountdownStart
                    preparedValid := false.B
                    measureValid := false.B
                }
                is(Q_RUN_CMD) {
                    val shotCount = io.cmd.bits.rs1(15, 0)
                    measureValid := false.B
                    when(preparedValid) {
                        for (i <- 0 until 4) {
                            runParamWords(i) := preparedParamWords(i)
                        }
                        runShots := shotCount
                        // Tutorial-scale quantum execution model: one cycle per requested shot.
                        runCounter := Mux(shotCount === 0.U, 0.U, shotCount - 1.U)
                        runBusy := true.B
                        runQueued := false.B
                    }.elsewhen(genBusy) {
                        queuedRunShots := shotCount
                        runQueued := true.B
                    }
                }
                is(Q_READ_CMD) {
                    // Compatibility path for the older paper-benchmark probes.
                    resp_data := perfCounter
                    state := s_resp
                }
                is(Q_READ_RUN_TIMES_CMD) {
                    // Older workloads poll this value until a q_run batch has completed.
                    resp_data := completedRunShots
                    state := s_resp
                }
            }
        }

        when(genBusy) {
            when(genCounter === 0.U) {
                for (i <- 0 until 4) {
                    preparedParamWords(i) := genParamWords(i)
                }
                preparedValid := true.B
                genBusy := false.B
                genEpoch := genEpoch + 1.U
                when(runQueued) {
                    for (i <- 0 until 4) {
                        runParamWords(i) := genParamWords(i)
                    }
                    runShots := queuedRunShots
                    // Tutorial-scale quantum execution model: one cycle per requested shot.
                    runCounter := Mux(queuedRunShots === 0.U, 0.U, queuedRunShots - 1.U)
                    runBusy := true.B
                    runQueued := false.B
                    measureValid := false.B
                }
            }.otherwise {
                genCounter := genCounter - 1.U
            }
        }

        when(runBusy) {
            when(runCounter === 0.U) {
                measureWord := Cat(1.U(2.W), runIter(7, 0), runSampleBits, runObjectivePpm, runTheta1, runTheta0)
                measureValid := true.B
                runBusy := false.B
                runEpoch := runEpoch + 1.U
                completedRunShots := completedRunShots + runShots
            }.otherwise {
                runCounter := runCounter - 1.U
            }
        }

        when((state === s_mem_req) && outer.mem_read.module.io.req.fire) {
            state := s_mem_wait
        }

        when((state === s_mem_wait) && !outer.mem_read.module.io.busy) {
            state := s_idle
        }

        when((state === s_acquire_wait) && measureValid) {
            resp_data := measureWord
            state := Mux(acquireResponseOnly, s_resp, s_acquire_req)
        }

        when((state === s_acquire_req) && io.mem.req.fire) {
            state := s_resp
        }

        when((state === s_resp) && io.resp.fire) {
            state := s_idle
        }

        // Send the request to dispatch
        outer.mem_read.module.io.req.valid := (state === s_mem_req)
        outer.mem_read.module.io.req.bits.op := funct
        outer.mem_read.module.io.req.bits.classic_addr := classic_addr
        outer.mem_read.module.io.req.bits.quantum_addr := quantum_addr
        outer.mem_read.module.io.req.bits.length := length

        // Connect mem_read output to the module based on quantum_addr
        /* Instruction address range : Instruction 0x000000000-0x07fffffff
           Each parameter take 16 bits aka 2 bytes. If the first instruction is at 0x000000000, then the second instruction is at 0x000000002, and so on.
           For each qubit, we allocate 1024 instructions.
           IT IS MUCH EASIER IF WE USE POWER OF 2
           So given a quantum address, we can determine the qubit number by dividing the quantum address by 1024*3
        */
        // use shift to determine the index
        outer.mem_read.module.io.output.ready := true.B
        index_table.io.write_req.valid := write_valid
        index_table.io.write_req.bits.write_type := Mux(q_update_direct_valid, IT_REGUPDATE, IT_INSSET)
        index_table.io.write_req.bits.addr := write_addr
        index_table.io.write_req.bits.length := write_length
        index_table.io.write_req.bits.data := write_data

        when(write_valid) {
            for (slot <- 0 until 4) {
                for (lane <- 0 until 8) {
                    when((write_length > lane.U) && (write_addr + lane.U === (tutorialParamBase + slot.U))) {
                        tutorialParamWords(slot) := write_data(15 + 16 * lane, 16 * lane)
                        touchedParamWindow := true.B
                    }
                }
            }
        }

        when(touchedParamWindow) {
            preparedValid := false.B
        }


        // Tutorial q_acquire mirrors the measurement word into host memory through the RoCC D-cache port.
        io.mem.req.valid := (state === s_acquire_req)
        io.mem.req.bits.addr := acquire_store_addr
        io.mem.req.bits.tag := 0.U
        io.mem.req.bits.cmd := M_XWR
        io.mem.req.bits.size := log2Ceil(xLen / 8).U
        io.mem.req.bits.signed := false.B
        io.mem.req.bits.data := Mux(measureValid, measureWord, 0.U)
        io.mem.req.bits.mask := fullStoreMask
        io.mem.req.bits.phys := false.B
        io.mem.req.bits.dprv := mem_dprv
        io.mem.req.bits.dv := mem_dv
        io.mem.req.bits.no_alloc := false.B
        io.mem.req.bits.no_xcpt := false.B
        io.mem.s1_kill := false.B
        io.mem.s2_kill := false.B
        io.mem.s1_data.data := RegNext(io.mem.req.bits.data, 0.U)
        io.mem.s1_data.mask := RegNext(io.mem.req.bits.mask, 0.U)
        io.mem.keep_clock_enabled := (state === s_acquire_req)
        // tl_out.b.ready := true.B
        // tl_out.c.valid := false.B
        // tl_out.e.valid := false.B
}

class QubitConnection extends Module {
    val io = IO(new Bundle {
        val dum_in = Input(UInt(16.W))
        val dum_out = Output(UInt(16.W))
    })
    dontTouch(io)
    io.dum_out := io.dum_in
}
