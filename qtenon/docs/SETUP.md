# Qtenon Tutorial Setup

## Modes

- **Default tutorial mode**: local replay from committed notebook artifacts,
  captures, and figures. This path should not require U200 access.
- **Maintainer mode**: U200-backed capture regeneration and hardware validation.
- **Current transition note**: some legacy helper code still reflects the older
  U200-coupled notebook flow until `04-21-qtenon-demo-rewrite` lands.

## Local Python Environment

Create and use the repo-local virtual environment:

```bash
cd code
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip numpy
```

If you want to execute or validate the notebook locally, install the notebook
runtime into the same `.venv`:

```bash
python -m pip install ipykernel nbformat nbclient IPython jupyterlab
python -m ipykernel install --prefix ./.venv --name qtenon-venv --display-name "Qtenon .venv"
```

If Qiskit is available or needed for legacy LUT generation:

```bash
python -m pip install qiskit
```

## Default Tutorial Path

The tutorial's default user workflow is replay-only:

- open `tutorial/qtenon_tutorial.ipynb`
- execute it locally with the repo-local kernel
- consume checked-in captures, objdumps, metadata, and figures from the repo

This path must not require:

- ssh access to U200
- a local RISC-V toolchain
- a local Verilator / Chipyard environment

## Maintainer: U200 Environment Script

The source of truth for the remote bootstrap lives at [`tools/tutorial_env.sh`](../tools/tutorial_env.sh).

Sync it to U200 with:

```bash
./tools/sync_to_u200.sh
```

Then on U200:

```bash
cd ~/firesim/target-design/chipyard
source tutorial_env.sh
```

## Maintainer: Sync Local Sources To U200

```bash
cd code
./tools/sync_to_u200.sh
```

Useful variants:

```bash
./tools/sync_to_u200.sh --dry-run
./tools/sync_to_u200.sh --host U200 --root ~/firesim/target-design/chipyard
```

Maintainers refreshing replay artifacts should then run:

```bash
./tutorial/scripts/refresh_captures.sh
```

## Run Helper Tests

```bash
cd code
PYTHONPATH=. python -m unittest discover -s tutorial/tests -t .
```
