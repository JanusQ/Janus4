package qc

import chisel3._
import chisel3.util._

object IndexTableWriteType {
    val IT_INSSET = 0.U
    val IT_REGUPDATE = 1.U
}

class WriteRequest extends Bundle {
    val addr = UInt(20.W)
    val data = UInt(61.W)
}

// class IndexTableWriteRequest extends Bundle {
//     val write_req = new WriteRequest
//     val index = UInt(10.W)
// }

class IndexTableWriteRequest extends Bundle {
    val write_type = UInt(2.W) // TODO: determine how many
    val addr = UInt(20.W)
    val length = UInt(4.W)
    val data = UInt(128.W)
}

// Type[3:0] Angle[15:4] V[16] C[17] Address[56:18]
class IndexTable(qubit_number: Int) extends Module {
    val io = IO(new Bundle{
        val write_req = Flipped(Decoupled(new IndexTableWriteRequest))
    })
    val mem = SyncReadMem(1024*qubit_number, UInt(57.W))

    // TODO: wheather we need state or not
    io.write_req.ready := true.B

    // Write operation
    when(io.write_req.fire){
        when(io.write_req.bits.write_type === IndexTableWriteType.IT_INSSET){
            // [0:15] is set according to the write_requst and [16:61] is set to 0
            val data = io.write_req.bits.data
            val length = io.write_req.bits.length
            for(i <- 0 until 8){
                when(length > i.U) {
                    val dataToWrite = Cat(data(15 + 16 * i, 16 * i), 0.U(41.W))
                    mem.write(io.write_req.bits.addr + i.U, dataToWrite)
                }
            }
        }.elsewhen(io.write_req.bits.write_type === IndexTableWriteType.IT_REGUPDATE){
            val data = io.write_req.bits.data
            val length = io.write_req.bits.length
            for(i <- 0 until 4){
                when(length > i.U) {
                    val dataToWrite = Cat(data(15 + 16 * i, 16 * i), 0.U(41.W))
                    mem.write(io.write_req.bits.addr + i.U, dataToWrite)
                }
            }
        }
    }
}

// class IndexTableWrapper(qubit_number: Int) extends Module {
//     val io = IO(new Bundle{
//         val write_req = Flipped(new IndexTableWriteRequest)
//     })
//     val index_tables = Seq.fill(qubit_number)(Module(new IndexTable))
//     // choose which index table to write to based on the index
//     for (i <- 0 until qubit_number) {
//         when (io.write_req.index === i.U) {
//             index_tables(i).io.write_req := io.write_req.write_req
//         }
//     }
// }
