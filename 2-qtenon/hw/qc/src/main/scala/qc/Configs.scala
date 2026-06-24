package qc

import chisel3._
import org.chipsalliance.cde.config.{Config, Parameters}
import freechips.rocketchip.diplomacy.LazyModule
import freechips.rocketchip.tile.BuildRoCC

class QuantumExtension extends Config((site, here, up) => {
  case BuildRoCC => up(BuildRoCC) ++ Seq(
    (p: Parameters) => {
      val qc = LazyModule(new QuantumController(4)(p))
      qc
    }
  )
})
