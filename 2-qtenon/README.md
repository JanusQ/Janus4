# Qtenon Tutorial Code

Standalone code repository for the Qtenon ISCA 2025 tutorial.

Paper, slides, and discussion docs live one level up in `ISCA2025-Qtenon/`.

---

## Quickstart (Docker — recommended)

```bash
docker pull janusq/janus4:isca2026
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

Open the printed `http://localhost:8888/lab` URL and run the
`2-qtenon/tutorial/qtenon_tutorial.ipynb` notebook end-to-end with the
`qtenon-venv` kernel. The image bakes the expensive Qtenon compile/simulation
artifacts during `docker build`, so normal notebook runs read the cached
`tutorial/runs/hybrid_loop/` files instead of re-running the slow Verilator
step. Set `QTENON_IGNORE_BAKED_CACHE=1` before launching the container when a
fresh live run is required. See
[`docs/DOCKER.md`](docs/DOCKER.md) for the Apple Silicon note and the
contributor rebuild flow.

For contributors editing helpers or hardware sources, see
[`docs/SETUP.md`](docs/SETUP.md) for the local-venv path and the validation environment
contributor flow.

---

## Workflow Split

- **Default tutorial path**: local replay from checked-in artifacts under
  `tutorial/`, especially captures, metadata, and figures. This is the
  path tutorial readers should use; it must not require validation environment access.
- **Contributor path**: validation environment remains the execution target for refreshing capture
  artifacts and validating hardware-side changes.
- **Current transition status**: the repo is being migrated from an older
  validation environment-coupled notebook flow to the replay-only local path. Until
  `04-21-qtenon-demo-rewrite` lands, some helpers or generated notebook cells
  may still contain legacy validation environment execution code.

---

## Directory Layout (target)

```text
code/
├── hw/
│   └── qc/                    # Scala HW source (mirrored to validation environment)
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
│   │   └── capture artifact flow
│   ├── tests/
│   │   ├── test_common.py
│   │   ├── test_encode.py
│   │   └── test_notebook_support.py
│   ├── build_notebook.py
│   ├── validate_notebook.py
│   └── qtenon_tutorial.ipynb
├── tools/
│   ├── source synchronization flow
│   └── environment setup
└── docs/
    └── SETUP.md
```

## Contributor Relationship to validation environment

- **Source of truth**: this repo
- **Contributor execution site**: validation environment at `chipyard checkout/`
- **Sync direction**: this repo → validation environment via `tools/source synchronization flow`
- **Chipyard tree on validation environment**: our files overwrite only:
  - `generators/qc/src/main/scala/qc/*.scala`
  - `generators/chipyard/src/main/scala/config/RoCCAcceleratorConfigs.scala`
  - `tests/hybrid_loop_demo.c`
  - `tests/rocc.h`
  - `environment setup`

## Edit Workflow

For hardware and capture contributors, develop locally on macOS, commit in this
repo, sync to validation environment, then run the simulator on validation environment:

```bash
./tools/source synchronization flow
validation environment 'cd chipyard checkout && source environment setup && make ...'
```

To refresh the checked-in tutorial replay artifacts, run
`./capture artifact generation flow` from this local repo.

For tutorial readers, the intended steady-state path is local notebook
execution against committed artifacts. validation environment should not be required just to run
the tutorial.

## Build / Run

See [`docs/SETUP.md`](docs/SETUP.md) for the local quickstart and the separate
contributor-only validation environment flow.

---

Status: source mirror and tutorial scaffolding in progress (Task: `qtenon-tutorial-infra`).
