# Tutorial Captures

These files are contributor-generated replay artifacts for the Qtenon tutorial.
They are not part of the attendee setup path.

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

The `hybrid_loop` trace is filtered from the raw `spike-dasm` `.out` produced
by `make run-binary` on validation environment. The `paper_vqe_spsa` capture intentionally keeps
only a trace placeholder; its notebook section reads the UART metric log.

## Refresh Flow

Run the contributor-only refresh script from the local `code/` repo:

```bash
cd code
./capture artifact generation flow
```

Requirements:

- working `validation environment`
- `tools/source synchronization flow` succeeds
- validation environment Chipyard tree at `chipyard checkout`
- QChipRocketConfig buildable on validation environment
- known-good Verilator at `/path/to/toolchain-env/bin/verilator`

Useful overrides:

```bash
QTENON_validation environment_HOST=validation environment \
QTENON_validation environment_CHIPYARD_ROOT=chipyard checkout \
QTENON_CONFIG_NAME=QChipRocketConfig \
QTENON_REBUILD_SIM=1 \
./capture artifact generation flow
```

If the host resolves an old system Verilator, keep the default
`QTENON_VERILATOR` override or point it at another `--main`-capable binary.
