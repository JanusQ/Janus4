# Docker — recommended attendee path

The Qtenon tutorial ships as a Docker image so attendees can run the notebook
end-to-end (cross-compile + Verilator simulation included) without installing a
local Python / Jupyter / RISC-V / Verilator toolchain.

---

## Attendee one-liner

```bash
docker pull janusq/qtenon:isca2026
docker run --rm -p 127.0.0.1:8888:8888 janusq/qtenon:isca2026
```

The container prints `http://localhost:8888/lab` (auth disabled — single-user
local container; bind to `127.0.0.1` to keep it off the network). Open the
URL, launch `qtenon_tutorial.ipynb`, and run **Restart Kernel and Run All
Cells**.

Cells [3] (`compile_elf`) and [14] (`run_local_sim`) execute the **live** path
inside the container — they cross-compile `hybrid_loop_demo.c` with the
bundled RISC-V toolchain and run the bundled Verilator simulator, so editing
the C source and re-running the cells reflects real retire-cycle deltas.

## Apple Silicon note

The image is `linux/amd64` only — the bundled Verilator simulator is the
x86_64 binary used by the published tutorial image, with no upstream arm64
build available for this tag.
On Apple Silicon (M-series) Macs, Docker Desktop runs the image under Rosetta:

```bash
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/qtenon:isca2026
```

Expect roughly **3× slowdown** on the cell [14] simulation under Rosetta
(≈ 5–6 min wallclock vs. ≈ 1–2 min on native amd64). All other cells finish
in under a second; only the Verilator step is dominated by emulation cost.

## What's in the image

- `python:3.11-slim-bookworm` base
- JupyterLab 4.x + ipykernel + nbformat + nbclient + matplotlib + numpy
- `qtenon-venv` kernelspec (matches the venv-based name from `SETUP.md`)
- RISC-V cross-compile toolchain at `/opt/qtenon-toolchain/` —
  `riscv64-unknown-elf-gcc` 12.2.0, `htif_nano.specs`, libgloss-htif, and
  matching libgmp / libmpfr / libmpc / libz
- Pre-built Verilator simulator at `/usr/local/bin/qtenon-sim` and the
  Chipyard-built `libriscv.so` / `libdramsim.so` at `/opt/qtenon-sim-libs/`
  (resolved via `LD_LIBRARY_PATH`)
- Tutorial content under `/workspace/code/` (the entire `code/` tree minus
  `.venv`, `runs/`, `__pycache__`, and host-only Trellis state — see
  `.dockerignore`)
- Environment hooks: `QTENON_RISCV_GCC`, `QTENON_SIMULATOR`,
  `LD_LIBRARY_PATH` are pre-set so `compile_elf` / `run_local_sim` find the
  bundled toolchain without a Chipyard tree on disk

## What's NOT in the image

- Chipyard, FIRRTL, sbt, JVM — the toolchain that **builds** the simulator.
  The image ships the prebuilt simulator needed for the tutorial path.
- spike-dasm — the trace filter on the Python side selects raw `custom0`
  lines and discards disassembly tokens, so we skip the dasm step entirely.
- The `build/` staging directory used during image construction (vendored
  toolchain tarball + simulator binary). It's gitignored on the host and not
  shipped in the image either; only the extracted artefacts under `/opt/`
  and `/usr/local/bin/` are present.

## Image rebuild flow

The image is rebuilt whenever the Verilator simulator, the toolchain tarball,
or the tutorial code changes. The expected staging inputs are:

- `build/simulator-chipyard.harness-QChipRocketConfig`
- `build/qtenon-toolchain-amd64.tar.gz`
- `build/qtenon-sim-libs-amd64.tar.gz`

Steps:

1. **Stage the simulator** at
   `build/simulator-chipyard.harness-QChipRocketConfig` and mark it
   executable.
2. **Stage the toolchain tarball** with archive root `qtenon-toolchain/`.
   Drop the resulting tarball at
   `build/qtenon-toolchain-amd64.tar.gz`.
3. **Stage the simulator libraries** — `libriscv.so` and `libdramsim.so`,
   stripped and packed as
   `build/qtenon-sim-libs-amd64.tar.gz`.
4. **Build** from repo root:
   ```bash
   docker build -t janusq/qtenon:isca2026 .
   ```
5. **Smoke test** before pushing:
   ```bash
   bash tutorial/scripts/smoke_docker.sh
   ```
   This rebuilds + runs `python -m tutorial.validate_notebook` inside the
   image and exits non-zero on any cell failure.
6. **Push** to Docker Hub (requires `docker login` with a credential
   authorized on the `janusq` org):
   ```bash
   docker push janusq/qtenon:isca2026
   ```
7. **Pin the digest** — record the resulting `sha256:…` here so attendees
   can pull deterministically: `docker pull janusq/qtenon@sha256:<digest>`.

### Published digest

For attendees who want a deterministic pull pinned to a specific build:

```bash
docker pull janusq/qtenon@sha256:8140d2e3bca30077c30b99dcbfa5b05f491dc51bf89dfe5b9ee5927262aeef42
```

| Tag | Digest | Date |
|---|---|---|
| `janusq/qtenon:isca2026` | `sha256:8140d2e3bca30077c30b99dcbfa5b05f491dc51bf89dfe5b9ee5927262aeef42` | 2026-04-27 |
