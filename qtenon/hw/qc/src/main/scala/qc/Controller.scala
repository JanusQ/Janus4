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
import TimeControllerISA._
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
        val s_idle :: s_mem_req :: s_mem_wait :: s_acquire_req :: s_resp :: Nil = Enum(5)
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

        // tutorial-visible minimal backend state
        val tutorialParamBase = "h0040".U(20.W)
        val tutorialParamWords = RegInit(VecInit(Seq.fill(4)(0.U(16.W))))
        val preparedParamWords = RegInit(VecInit(Seq.fill(4)(0.U(16.W))))
        val preparedValid = RegInit(false.B)
        val genEpoch = RegInit(0.U(8.W))
        val runEpoch = RegInit(0.U(8.W))
        val measureWord = RegInit(0.U(64.W))
        val measureValid = RegInit(false.B)
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
        val activeParamWords = Wire(Vec(4, UInt(16.W)))

        for (i <- 0 until 4) {
            activeParamWords(i) := Mux(preparedValid, preparedParamWords(i), tutorialParamWords(i))
        }

        // CONNECTION for the accelerator
        // TODO: add more delicite control
        // TODO: the ready signal for io.cmd.ready
        io.cmd.ready := (state === s_idle)
        io.busy := (state =/= s_idle)
        io.resp.valid := (state === s_resp)
        io.resp.bits.rd := resp_rd
        io.resp.bits.data := resp_data

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
                    // Return the latest measurement word and mirror it into host memory when a buffer is provided.
                    resp_data := Mux(measureValid, measureWord, 0.U)
                    acquire_store_addr := io.cmd.bits.rs1(acquireStoreAddrWidth - 1, 0)
                    state := Mux(io.cmd.bits.rs1 === 0.U, s_resp, s_acquire_req)
                }
                is(Q_UPDATE_CMD) {
                    state := s_idle
                }
                is(Q_GEN_CMD) {
                    for (i <- 0 until 4) {
                        preparedParamWords(i) := tutorialParamWords(i)
                    }
                    preparedValid := true.B
                    genEpoch := genEpoch + 1.U
                }
                is(Q_RUN_CMD) {
                    val activeTheta0 = activeParamWords(0)
                    val activeTheta1 = activeParamWords(1)
                    val activeIter = activeParamWords(2)
                    val scoreWide = Wire(UInt(21.W))
                    val objectivePpm = Wire(UInt(20.W))
                    val sampleMix = Wire(UInt(8.W))
                    val sampleBits = Wire(UInt(2.W))

                    scoreWide := (activeTheta0 * 37.U) + (activeTheta1 * 19.U) +
                                 (activeIter * 53.U) + io.cmd.bits.rs1(15, 0) + genEpoch + runEpoch
                    objectivePpm := Mux(scoreWide(19, 0) >= 1000000.U, scoreWide(19, 0) - 1000000.U, scoreWide(19, 0))
                    sampleMix := objectivePpm(7, 0) ^ activeTheta0(7, 0) ^ activeTheta1(7, 0) ^
                                 activeIter(7, 0) ^ io.cmd.bits.rs1(7, 0)
                    sampleBits := sampleMix(1, 0)

                    measureWord := Cat(1.U(2.W), activeIter(7, 0), sampleBits, objectivePpm, activeTheta1, activeTheta0)
                    measureValid := true.B
                    runEpoch := runEpoch + 1.U
                }
            }
        }

        when((state === s_mem_req) && outer.mem_read.module.io.req.fire) {
            state := s_mem_wait
        }

        when((state === s_mem_wait) && !outer.mem_read.module.io.busy) {
            state := s_idle
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


        // outer.time_controller.module.io.cmd.valid := (state === s_issue && (is_q_gen || is_q_run))
        // outer.time_controller.module.io.cmd.bits.op := MuxLookup(funct, 0.U, Seq(
        //     Q_GEN_CMD -> CACHE,
        //     Q_RUN_CMD -> ISSUE
        // ))
        // outer.time_controller.module.io.cmd.bits.mem := rs1(38, 0)
        // outer.time_controller.module.io.cmd.bits.local := rs2(38, 0)
        // outer.time_controller.module.io.cmd.bits.length := rs2(54, 39)

        // when(outer.time_controller.module.io.cmd.fire) {state := s_idle}

        // TODO: determine what is the virtual address of Linux

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
