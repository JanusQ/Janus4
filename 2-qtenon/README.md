# Qtenon Tutorial Code

Standalone code repository for the Qtenon ISCA 2025 tutorial.

Paper, slides, and discussion docs live one level up in `ISCA2025-Qtenon/`.

---

## Quickstart (Docker — recommended)

```bash
docker pull janusq/qtenon:isca2026
docker run --rm -p 127.0.0.1:8888:8888 janusq/qtenon:isca2026
```

Open the printed `http://localhost:8888/lab` URL and run the
`qtenon_tutorial.ipynb` notebook end-to-end. Cells [3] / [14] cross-compile
and run the Verilator simulator live inside the container — no local
Python / Jupyter / RISC-V / Verilator setup needed. See
[`docs/DOCKER.md`](docs/DOCKER.md) for the Apple Silicon note and image
contents.

For contributors editing helpers or hardware sources, see
[`docs/SETUP.md`](docs/SETUP.md) for the local-venv path and optional live
simulation prerequisites.

---

## Workflow Split

- **Default tutorial path**: local replay from checked-in artifacts under
  `tutorial/`, especially captures, metadata, and figures. This is the
  path tutorial readers should use; it does not require Chipyard, Verilator,
  or a RISC-V toolchain on the host machine.
- **Contributor path**: local Python tooling can validate notebook helpers and
  replay artifacts without a hardware build environment.
- **Advanced live path**: users with a compatible Chipyard/Verilator setup can
  opt into live simulator runs through environment variables documented in the
  notebook.

---

## Directory Layout (target)

```text
code/
├── hw/
│   └── qc/                    # Scala HW source for the RoCC accelerator
│       └── src/main/scala/
│           ├── qc/
│           │   ├── ISA.scala
│           │   ├── Configs.scala
│           │   ├── IndexTable.scala
│           │   ├── Dispatch.scala
│           │   ├── Controller.scala
│           │   └── TimeController.scala
│           └── config/
│               └── RoCCAcceleratorConfigs.scala
├── software/
│   └── tests/
│       ├── hybrid_loop_demo.c
│       └── rocc.h
├── tutorial/
│   ├── helpers/
│   │   ├── common.py
│   │   ├── encode.py
│   │   ├── notebook_support.py
│   │   └── trace.py
│   ├── figures/
│   ├── captures/
│   │   └── hybrid_loop/
│   ├── scripts/
│   │   ├── build_smoke_cache.sh
│   │   └── smoke_docker.sh
│   ├── tests/
│   │   ├── test_common.py
│   │   ├── test_encode.py
│   │   └── test_notebook_support.py
│   ├── build_notebook.py
│   ├── validate_notebook.py
│   └── qtenon_tutorial.ipynb
└── docs/
    ├── DOCKER.md
    └── SETUP.md
```

## Edit Workflow

For tutorial helper changes, develop locally and run the helper test suite:

```bash
PYTHONPATH=. python -m unittest discover -s tutorial/tests -t .
```

For hardware or live-simulator changes, use a compatible Chipyard checkout and
set `QTENON_CHIPYARD_ROOT` / `QTENON_CONFIG_NAME` as needed. The public
tutorial path remains replay-based and runs from committed artifacts.

## Build / Run

See [`docs/SETUP.md`](docs/SETUP.md) for the local contributor setup and
[`docs/DOCKER.md`](docs/DOCKER.md) for the attendee Docker path.

---

Status: source mirror and tutorial scaffolding in progress (Task: `qtenon-tutorial-infra`).
