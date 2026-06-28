# Tutorial Captures

These files are checked-in replay artifacts for the Qtenon tutorial. They keep
the notebook runnable without requiring a local hardware-simulation setup.

## What Lives Here

- `hybrid_loop/`: 4-iteration Act 3 `q_set/q_update -> q_gen -> q_run -> q_acquire` evidence
- `paper_vqe_spsa/`: 64-qubit VQE/SPSA paper time-breakdown reproduction
  evidence for `pic/experiment/time_breakdown.pdf`; this capture is
  log-driven and uses `run-binary-fast` because the paper rdcycle replay
  windows would otherwise generate hundreds of megabytes of instruction trace
- `meta.json`: schema version, capture date, git identity, hw/tutorial subtree SHAs, config hash, Verilator version, and ELF hashes

Each capture directory contains:

- `<name>.elf`
- `<name>.objdump.txt`
- `<name>.trace.txt`
- `<name>.log`

The `hybrid_loop` trace is filtered from a simulator retire trace. The
`paper_vqe_spsa` capture intentionally keeps only a trace placeholder; its
notebook section reads the UART metric log.

Regenerating these files requires a compatible Chipyard/Verilator environment
and should be done before updating this directory in the public tutorial tree.
