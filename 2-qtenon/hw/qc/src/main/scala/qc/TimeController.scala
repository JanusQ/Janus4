package qc

import chisel3._
import chisel3.util._

import freechips.rocketchip.diplomacy._
import org.chipsalliance.cde.config._
import freechips.rocketchip.tile._
import freechips.rocketchip.rocket._
import freechips.rocketchip.tilelink._

import TimeControllerISA._

class TimeController(implicit p: Parameters) extends LazyModule {
    val id_node = TLIdentityNode()
    val xbar_node = TLXbar()
    val mem_node = TLClientNode(Seq(TLMasterPortParameters.v1(Seq(TLClientParameters(
    name = "time_controller_mem", sourceId = IdRange(0, 4))))))

    xbar_node := TLBuffer() := mem_node
    id_node := TLWidthWidget(128/8) := TLBuffer() := xbar_node

    lazy val module = new Impl
    class Impl extends LazyModuleImp(this){
        val (tl, edge) = mem_node.out(0)
        val io = IO(new Bundle {
            val cmd = Flipped(Decoupled(new Bundle{
                val op     = UInt(2.W)
                val mem    = UInt(39.W)
                val local  = UInt(39.W)
                val length = UInt(15.W)
            }))
        })
        // state machine
        val s_idle :: c_fetch :: wave_fetch :: issue :: Nil = Enum(4)
        val state = RegInit(s_idle)

        // Outer connection
        io.cmd.ready := (state === s_idle)
        val func_type = Reg(UInt(2.W))
        func_type := io.cmd.bits.op

        // index part
        val xy_index = SyncReadMem(1024, UInt(42.W))
        val z_index  = SyncReadMem(1024, UInt(42.W))

        // cache part
        val cache_xy = SyncReadMem(1024 * 32, UInt(16.W))
        val cache_xy_length = RegInit(0.U(15.W))
        val cache_z  = SyncReadMem(1024 * 32, UInt(16.W))

        val xy_length = RegInit(0.U(10.W))
        val cur_index = RegInit(0.U(10.W)) // TODO: add a value to maintain the cached index

        // TEMP: value for the address
        val req_addr = Reg(UInt(39.W))
        val req_type = Reg(UInt(3.W))
        val req_valid = RegInit(false.B)

        // Value for WAVESET operation
        val mem_base = Reg(UInt(39.W))
        val write_cache_addr = Reg(UInt(15.W))
        val write_cache_length = Reg(UInt(15.W))
        val write_counter = Reg(UInt(2.W))

        // Value for ISSUE operation
        val issue_data = Reg(UInt(16.W))
        val issue_addr = RegInit(0.U(15.W))

        // intermidiate value
        val xy_data = Reg(UInt(42.W))
        val id = RegInit(0.U(2.W))

        // Add outer connection
        val qubit_xy = Module(new QubitConnection)
        qubit_xy.io.dum_in := issue_data

        when(io.cmd.fire) {
            switch(io.cmd.bits.op) {
                is(CACHE) {
                    cur_index := 0.U
                    state := c_fetch
                }
                is(WAVESET) {
                    state := wave_fetch
                    mem_base := io.cmd.bits.mem
                    write_cache_addr := io.cmd.bits.local
                    write_cache_length := io.cmd.bits.length
                    write_counter := 0.U
                }
                is(ISSUE) {
                    state := issue
                    issue_addr := 0.U
                }
            }
        }

        // Tilelink information
        val tl_a = chiselTypeOf(tl.a.bits)
        val tl_a_queue = Module(new Queue(tl_a, 4))
        val get = edge.Get(
            fromSource = id,
            toAddress = MuxCase(state, Seq(
                (state === c_fetch) -> req_addr,
                (state === wave_fetch) -> mem_base,
                (state === s_idle) -> 0.U
            )),
            lgSize = 4.U
        )._2

        val tl_d = chiselTypeOf(tl.d.bits)
        val tl_d_queue = Module(new Queue(tl_d, 4))

        when(tl_a_queue.io.enq.fire && !tl_d_queue.io.deq.fire) {
            write_counter := write_counter + 1.U
        }.elsewhen(tl_d_queue.io.deq.fire && !tl_a_queue.io.enq.fire) {
            write_counter := write_counter - 1.U
        }

        // TODO: check sequence
        // TODO: take all state out to meet the time demand
        switch(state) {
            is(s_idle) {
                // Do nothing
            }
            is(c_fetch) {
                when(cur_index < xy_length) {
                    // Request data from xy_index
                    xy_data := xy_index.read(cur_index)
                    req_addr := xy_data(38, 0)
                    req_type := xy_data(41, 39)
                    req_valid := RegNext(true.B)

                    // Check if the queue is full
                    when(tl_a_queue.io.enq.ready && req_valid) {
                        id := id + 1.U
                        cur_index := cur_index + 1.U
                    }
                }.otherwise {
                    state := s_idle
                    req_valid := false.B
                }
                // TODO: add channel D
            }
            // TODO: this
            is(wave_fetch) {
                // TODO: magic number
                when(tl_a_queue.io.enq.fire) {
                    id := id + 1.U
                    when(write_cache_length >= 16.U){
                        mem_base := mem_base + 16.U
                        write_cache_length := write_cache_length - 16.U
                    }
                }
                // Get the data and write to cache
                when(tl_d_queue.io.deq.fire) {
                    cache_xy.write(write_cache_addr, tl_d_queue.io.deq.bits.data(15, 0))
                    cache_xy.write(write_cache_addr + 1.U, tl_d_queue.io.deq.bits.data(31, 16))
                    cache_xy.write(write_cache_addr + 2.U, tl_d_queue.io.deq.bits.data(47, 32))
                    cache_xy.write(write_cache_addr + 3.U, tl_d_queue.io.deq.bits.data(63, 48))
                    cache_xy.write(write_cache_addr + 4.U, tl_d_queue.io.deq.bits.data(79, 64))
                    cache_xy.write(write_cache_addr + 5.U, tl_d_queue.io.deq.bits.data(95, 80))
                    cache_xy.write(write_cache_addr + 6.U, tl_d_queue.io.deq.bits.data(111, 96))
                    cache_xy.write(write_cache_addr + 7.U, tl_d_queue.io.deq.bits.data(127, 112))
                    cache_xy_length := cache_xy_length + 8.U

                    write_cache_addr := write_cache_addr + 8.U
                }
                when(write_counter === 0.U && write_cache_length < 16.U) {
                    state := s_idle
                }
            }
            is(issue) {
                when(issue_addr <= cache_xy_length) {
                    issue_data := cache_xy.read(issue_addr, true.B)
                    issue_addr := issue_addr + 1.U
                }.otherwise {
                    state := s_idle
                }
            }
        }


        // when((state === issue) && (issue_addr < cache_xy_length)) {
        //     issue_data := cache_xy.read(issue_addr, true.B)
        //     issue_addr := issue_addr + 1.U
        // }

        // Connection for tilelink
        // TODO: add logic for CACHE operation
        tl_a_queue.io.enq.valid := ((state === wave_fetch) && (write_cache_length >= 16.U))
        tl_a_queue.io.enq.bits  := get
        tl.a <> tl_a_queue.io.deq
        tl_d_queue.io.enq <> tl.d
        tl_d_queue.io.deq.ready := (state === wave_fetch)

        // Tie off unused channels
        tl.b.ready := true.B
        tl.c.valid := false.B
        tl.e.valid := false.B
    }
}
