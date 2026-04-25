# Qtenon Tutorial Setup

## Modes

- **Default tutorial mode**: local replay from committed notebook artifacts,
  captures, and figures. This path should not require validation environment access.
- **Contributor mode**: validation environment-backed capture regeneration and hardware validation.
- **Current transition note**: some legacy helper code still reflects the older
  validation environment-coupled notebook flow until `04-21-qtenon-demo-rewrite` lands.

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

- validation environment access
- a local RISC-V toolchain
- a local Verilator / Chipyard environment

## Contributor: validation environment Environment Script

The source of truth for the remote bootstrap lives at [`tools/environment setup`](../tools/environment setup).

Sync it to validation environment with:

```bash
./tools/source synchronization flow
```

Then on validation environment:

```bash
cd chipyard checkout
source environment setup
```

## Contributor: Sync Local Sources To validation environment

```bash
cd code
./tools/source synchronization flow
```

Useful variants:

```bash
./tools/source synchronization flow --dry-run
./tools/source synchronization flow --host validation environment --root chipyard checkout
```

Contributors refreshing replay artifacts should then run:

```bash
./capture artifact generation flow
```

## Run Helper Tests

```bash
cd code
PYTHONPATH=. python -m unittest discover -s tutorial/tests -t .
```
