# Qtenon Tutorial Code

Standalone code repository for the Qtenon ISCA 2025 tutorial.

Paper, slides, and discussion docs live one level up in `ISCA2025-Qtenon/`.

---

## Workflow Split

- **Default tutorial path**: local replay from checked-in artifacts under
  `tutorial/`, especially captures, metadata, and figures. This is the
  path tutorial readers should use; it must not require U200 access.
- **Maintainer path**: U200 remains the execution target for refreshing capture
  artifacts and validating hardware-side changes.
- **Current transition status**: the repo is being migrated from an older
  U200-coupled notebook flow to the replay-only local path. Until
  `04-21-qtenon-demo-rewrite` lands, some helpers or generated notebook cells
  may still contain legacy U200 execution code.

---

## Directory Layout (target)

```text
code/
├── hw/
│   └── qc/                    # Scala HW source (mirrored to U200)
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
│   │   └── refresh_captures.sh
│   ├── tests/
│   │   ├── test_common.py
│   │   ├── test_encode.py
│   │   └── test_notebook_support.py
│   ├── build_notebook.py
│   ├── validate_notebook.py
│   └── qtenon_tutorial.ipynb
├── tools/
│   ├── sync_to_u200.sh
│   └── tutorial_env.sh
└── docs/
    └── SETUP.md
```

## Maintainer Relationship to U200

- **Source of truth**: this repo
- **Maintainer execution site**: U200 at `~/firesim/target-design/chipyard/`
- **Sync direction**: this repo → U200 via `tools/sync_to_u200.sh`
- **Chipyard tree on U200**: our files overwrite only:
  - `generators/qc/src/main/scala/qc/*.scala`
  - `generators/chipyard/src/main/scala/config/RoCCAcceleratorConfigs.scala`
  - `tests/hybrid_loop_demo.c`
  - `tests/rocc.h`
  - `tutorial_env.sh`

## Edit Workflow

For hardware and capture maintainers, develop locally on macOS, commit in this
repo, sync to U200, then run the simulator on U200:

```bash
./tools/sync_to_u200.sh
ssh U200 'cd ~/firesim/target-design/chipyard && source tutorial_env.sh && make ...'
```

To refresh the checked-in tutorial replay artifacts, run
`./tutorial/scripts/refresh_captures.sh` from this local repo.

For tutorial readers, the intended steady-state path is local notebook
execution against committed artifacts. U200 should not be required just to run
the tutorial.

## Build / Run

See [`docs/SETUP.md`](docs/SETUP.md) for the local quickstart and the separate
maintainer-only U200 flow.

---

Status: source mirror and tutorial scaffolding in progress (Task: `qtenon-tutorial-infra`).
