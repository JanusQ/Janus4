# Qtenon Tutorial Setup

> **Attendees: skip this file.** The recommended path is the Docker image —
> see [`DOCKER.md`](DOCKER.md) for the one-line `docker pull` + `docker run`
> snippet. This file is for contributors editing helpers, hardware sources,
> or capture regeneration.

## Modes

- **Default attendee mode**: Docker image — see [`DOCKER.md`](DOCKER.md).
- **Contributor mode**: local Python venv against committed notebook
  artifacts, captures, and figures. No validation environment access required.
- **Contributor mode**: validation environment-backed capture regeneration and hardware
  validation.

## Docker (recommended)

```bash
docker pull janusq/janus4:isca2026
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

Opens JupyterLab on `http://localhost:8888/lab` with the tutorial notebook
ready to run end-to-end at `2-qtenon/tutorial/qtenon_tutorial.ipynb`
(cells [3] / [14] cross-compile and run the Verilator simulator live inside
the container). See [`DOCKER.md`](DOCKER.md) for the full attendee guide and
the contributor rebuild flow.

## Local Python Environment

> Use this path only if you need to edit helpers in `tutorial/helpers/`,
> hardware sources in `hw/`, or rebuild capture artefacts from validation environment.
> Attendees should use Docker (see above).

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

- open `2-qtenon/tutorial/qtenon_tutorial.ipynb` in the Janus4 image, or
  `tutorial/qtenon_tutorial.ipynb` when working directly inside `2-qtenon/`
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
