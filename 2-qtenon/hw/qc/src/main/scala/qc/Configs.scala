package qc

import chisel3._
import org.chipsalliance.cde.config.{Config, Parameters}
import freechips.rocketchip.diplomacy.LazyModule
import freechips.rocketchip.subsystem._
import freechips.rocketchip.tile.{BuildRoCC, OpcodeSet, XLen}
import freechips.rocketchip.rocket._
import freechips.rocketchip.tile._
import freechips.rocketchip.system._
import freechips.rocketchip.diplomacy._

import hardfloat._

class QuantumExtension extends Config((site, here, up) => {
  case BuildRoCC => up(BuildRoCC) ++ Seq(
    (p: Parameters) => {
      val qc = LazyModule(new QuantumController(4)(p))
      qc
    }
  )
})
