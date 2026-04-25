package qc

import chisel3._
import chisel3.util._
import chisel3.experimental.DataMirror

import org.chipsalliance.cde.config.Parameters
import freechips.rocketchip.diplomacy._
import freechips.rocketchip.tilelink._
import freechips.rocketchip.tile._

// read the data from the classic address and put it in the QC
class QCMemReadRequest extends Bundle {
    val op = UInt(3.W)
    val length = UInt(25.W)
    val classic_addr = UInt(39.W)
    val quantum_addr = UInt(39.W)
}

class QCMemReadOutput extends Bundle {
    val quantum_addr = UInt(39.W)
    val data = UInt(128.W)
    val length = UInt(4.W)
}

class MemReadInfo extends Bundle {
    val quantum_addr = UInt(39.W)
    val length = UInt(4.W)
    val offset_words = UInt(3.W)
}

// TODO: VERIFY
// 1. can it run
// 2. what if length is not a multiple of 16
class MemReadCore(implicit p: Parameters) extends LazyModule {
    val node = TLClientNode(Seq(TLMasterPortParameters.v1(Seq(TLClientParameters(
    name = "mem-read", sourceId = IdRange(0, 4))))))

    lazy val module = new Impl
    class Impl extends LazyModuleImp(this) with HasCoreParameters {
        val (tl, edge) = node.out(0)

        val io = IO(new Bundle {
            val req = Flipped(Decoupled(new QCMemReadRequest))
            val output = Decoupled(new QCMemReadOutput)
            val busy = Output(Bool())
        })

        // state machine
        val s_idle :: s_send_req :: s_wait_resp :: Nil = Enum(3)
        val state = RegInit(s_idle)

        // register
        val addr = RegInit(0.U(39.W))
        val quantum_addr = RegInit(0.U(39.W))
        val length_left = RegInit(0.U(25.W))
        val offset_words = RegInit(0.U(3.W))
        val is_first_block = RegInit(false.B)

        val words_per_beat = 8.U(25.W)
        val usable_words_this_beat = Mux(is_first_block, words_per_beat - offset_words, words_per_beat)
        val transferred_words = Mux(length_left >= usable_words_this_beat, usable_words_this_beat, length_left)

        io.req.ready := (state === s_idle)
        io.busy := (state =/= s_idle)

        // tilelink information
        val get = edge.Get(
            fromSource = 0.U,
            toAddress = addr,
            lgSize = 4.U
        )._2

        val shifted_data = tl.d.bits.data >> (offset_words << 4)

        io.output.valid := (state === s_wait_resp) && tl.d.valid
        io.output.bits.quantum_addr := quantum_addr
        io.output.bits.length := transferred_words(3, 0)
        io.output.bits.data := shifted_data

        when(io.req.fire) {
            state := s_send_req

            addr := Cat(io.req.bits.classic_addr(38, 4), 0.U(4.W))
            quantum_addr := io.req.bits.quantum_addr
            length_left := io.req.bits.length
            offset_words := io.req.bits.classic_addr(3, 1)
            is_first_block := true.B
        }

        when((state === s_send_req) && tl.a.fire) {
            state := s_wait_resp
        }

        when((state === s_wait_resp) && tl.d.fire) {
            when(length_left === transferred_words) {
                state := s_idle
                length_left := 0.U
            }.otherwise {
                state := s_send_req
                addr := addr + 16.U
                quantum_addr := quantum_addr + transferred_words
                length_left := length_left - transferred_words
                offset_words := 0.U
                is_first_block := false.B
            }
        }

        tl.a.valid := (state === s_send_req) && (length_left =/= 0.U)
        tl.a.bits := get
        tl.d.ready := io.output.ready && (state === s_wait_resp)
        tl.b.ready := true.B
        tl.c.valid := false.B
        tl.e.valid := false.B
    }
}

class Dispatch extends Module {
    val io = IO(new Bundle {
        val cmd = Flipped(Decoupled(new QCMemReadRequest))
    })

    // TODO: add command queue

}
