# Qtenon Tutorial Setup

> **Attendees: skip this file.** The recommended path is the Docker image —
> see [`DOCKER.md`](DOCKER.md) for the one-line `docker pull` + `docker run`
> snippet. This file is for contributors editing helpers, hardware sources,
> or local simulator integration.

## Modes

- **Default attendee mode**: Docker image — see [`DOCKER.md`](DOCKER.md).
- **Contributor mode**: local Python venv against committed notebook
  artifacts, captures, and figures.
- **Advanced live-simulation mode**: optional Chipyard/Verilator execution for
  users with a compatible local or remote hardware-simulation environment.

## Docker (recommended)

```bash
docker pull janusq/qtenon:isca2026
docker run --rm -p 127.0.0.1:8888:8888 janusq/qtenon:isca2026
```

Opens JupyterLab on `http://localhost:8888/lab` with the tutorial notebook
ready to run end-to-end (cells [3] / [14] cross-compile and run the
Verilator simulator live inside the container). On Apple Silicon, prepend
`--platform linux/amd64`. See [`DOCKER.md`](DOCKER.md) for the full
attendee guide and image details.

## Local Python Environment

> Use this path only if you need to edit helpers in `tutorial/helpers/`,
> hardware sources in `hw/`, or validate notebook artifacts locally.
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

- open `tutorial/qtenon_tutorial.ipynb`
- execute it locally with the repo-local kernel
- consume checked-in captures, objdumps, metadata, and figures from the repo

This path must not require:

- a local RISC-V toolchain
- a local Verilator / Chipyard environment

## Optional Live Simulation

If you have a compatible Chipyard checkout and Verilator simulator, point the
notebook helpers at that environment:

```bash
export QTENON_CHIPYARD_ROOT=chipyard-checkout
export QTENON_CONFIG_NAME=QChipRocketConfig
export QTENON_RUN_LIVE_SIM=1
```

The Docker image already carries the tutorial's supported live path, so most
users do not need this setup.

## Run Helper Tests

```bash
cd code
PYTHONPATH=. python -m unittest discover -s tutorial/tests -t .
```
