# Tutorial Captures

These files are maintainer-generated replay artifacts for the Qtenon tutorial.
They are not part of the attendee setup path.

## What Lives Here

- `hybrid_loop/`: 4-iteration Act 3 `q_set/q_update -> q_gen -> q_run -> q_acquire` evidence
- `meta.json`: schema version, capture date, git identity, hw/tutorial subtree SHAs, config hash, Verilator version, and ELF hashes

Each capture directory contains:

- `<name>.elf`
- `<name>.objdump.txt`
- `<name>.trace.txt`
- `<name>.log`

The trace files are the raw `spike-dasm` `.out` artifacts produced by
`make run-binary` on U200. They stay small enough to check in directly.

## Refresh Flow

Run the maintainer-only refresh script from the local `code/` repo:

```bash
cd code
./tutorial/scripts/refresh_captures.sh
```

Requirements:

- working `ssh U200`
- `tools/sync_to_u200.sh` succeeds
- U200 Chipyard tree at `~/firesim/target-design/chipyard`
- QChipRocketConfig buildable on U200
- known-good Verilator at `/home/taochenning/firesim/.conda-env/bin/verilator`

Useful overrides:

```bash
QTENON_U200_HOST=U200 \
QTENON_U200_CHIPYARD_ROOT=~/firesim/target-design/chipyard \
QTENON_CONFIG_NAME=QChipRocketConfig \
QTENON_REBUILD_SIM=1 \
./tutorial/scripts/refresh_captures.sh
```

If the host resolves an old system Verilator, keep the default
`QTENON_VERILATOR` override or point it at another `--main`-capable binary.
