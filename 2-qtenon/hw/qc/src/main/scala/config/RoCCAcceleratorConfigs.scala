package chipyard

import org.chipsalliance.cde.config.{Config}

class QChipRocketConfig extends Config(
  new qc.QuantumExtension ++
  new freechips.rocketchip.subsystem.WithNBigCores(1) ++
  new freechips.rocketchip.subsystem.WithExtMemSize((1<<30) * 4L) ++  // 4GB simulated external memory
  new freechips.rocketchip.subsystem.WithNMemoryChannels(2) ++
  new chipyard.config.WithSystemBusWidth(128) ++
  new chipyard.config.AbstractConfig)
