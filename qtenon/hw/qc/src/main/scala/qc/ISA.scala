package qc

import chisel3._

object QunatumControllerISA {
    // funct values
    val Q_SET_CMD     = 0.U
    val Q_UPDATE_CMD  = 1.U
    val Q_RUN_CMD     = 4.U
    val Q_GEN_CMD     = 5.U
    val Q_ACQUIRE_CMD = 6.U
}

object TimeControllerISA {
    val CACHE   = 0.U
    val WAVESET = 1.U
    val ISSUE   = 2.U
}
