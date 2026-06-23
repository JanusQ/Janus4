# Janus4 Docker — recommended attendee path

The Janus4 tutorial ships as one Docker image. Qtenon runs inside that image
with its own `qtenon-venv` kernel, so attendees can run the notebook end-to-end
(cross-compile + Verilator simulation included) without installing a local
Python / Jupyter / RISC-V / Verilator toolchain.

---

## Attendee one-liner

```bash
docker pull janusq/janus4:isca2026
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

The container prints `http://localhost:8888/lab` (auth disabled — single-user
local container; bind to `127.0.0.1` to keep it off the network). Open the
URL, launch `2-qtenon/tutorial/qtenon_tutorial.ipynb`, select the
`qtenon-venv` kernel, and run **Restart Kernel and Run All Cells**.

Cells [3] (`compile_elf`) and [14] (`run_local_sim`) read the baked
`tutorial/runs/hybrid_loop/` cache by default. That cache is generated during
`docker build` from the bundled RISC-V toolchain and Verilator simulator, so
normal attendee notebook runs avoid the slow simulation step. To force a fresh
live run after editing the C source, launch the container with
`-e QTENON_IGNORE_BAKED_CACHE=1`.

## Apple Silicon note

The image is `linux/amd64` only — the bundled Verilator simulator is the
x86_64 binary built on the validation environment host, with no upstream arm64 build available.
On Apple Silicon (M-series) Macs, Docker Desktop runs the image under Rosetta:

```bash
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

Expect roughly **3× slowdown** when forcing the cell [14] live simulation under
Rosetta (≈ 5–6 min wallclock vs. ≈ 1–2 min on native amd64). With the default
baked cache, normal notebook execution avoids that slow path.

## What's in the image

- `python:3.11-slim-bookworm` base
- JupyterLab 4.x + ipykernel + nbformat + nbclient + matplotlib + numpy
- `qtenon-venv` kernelspec (matches the venv-based name from `SETUP.md`)
- `artery` kernelspec for the ARTERY feedback topic
- `adaptiveqc` kernelspec for the AdaptDQC topic
- `chocoq` kernelspec for the Choco-Q topic
- `qram` kernelspec for the EXP-QRAM topic
- RISC-V cross-compile toolchain at `/opt/qtenon-toolchain/` —
  `riscv64-unknown-elf-gcc` 12.2.0, `htif_nano.specs`, libgloss-htif, and
  matching libgmp / libmpfr / libmpc / libz
- Pre-built Verilator simulator at `/usr/local/bin/qtenon-sim` and the
  Chipyard-built `libriscv.so` / `libdramsim.so` at `/opt/qtenon-sim-libs/`
  (resolved via `LD_LIBRARY_PATH`)
- Tutorial content under `/workspace/`, including the numbered topic tree
  `2-qtenon/` through `6-EXP-QRAM/` (host-only caches and generated outputs are
  excluded by the root `.dockerignore`)
- Environment hooks: `QTENON_RISCV_GCC`, `QTENON_SIMULATOR`,
  `LD_LIBRARY_PATH` are pre-set so `compile_elf` / `run_local_sim` find the
  bundled toolchain without a Chipyard tree on disk

## What's NOT in the image

- Chipyard, FIRRTL, sbt, JVM — the contributor-only chain that **builds** the
  simulator. To rebuild the simulator, see the validation environment flow in
  [`SETUP.md`](SETUP.md) (contributor section).
- spike-dasm — the trace filter on the Python side selects raw `custom0`
  lines and discards disassembly tokens, so we skip the dasm step entirely.
- The `build/` staging directory used during image construction (vendored
  toolchain tarball + simulator binary). It's gitignored on the host and not
  shipped in the image either; only the extracted artefacts under `/opt/`
  and `/usr/local/bin/` are present.

## Contributor rebuild flow

The Janus4 image is built from the repository root. It uses
`janusq/qtenon:isca2026` as the base layer for the Qtenon toolchain/simulator,
then adds the numbered Janus4 topic tree and topic-specific kernels.

If the Qtenon Verilator simulator or RISC-V toolchain changes, refresh and
publish the Qtenon base image first. The historical base-image rebuild flow is:

1. **Stage the simulator** — on validation environment, build
   `simulator-chipyard.harness-QChipRocketConfig`, then copy it to the host's
   `build/` directory:
   ```bash
   copy validation environment artifact from chipyard checkout/sims/verilator/simulator-chipyard.harness-QChipRocketConfig \
       build/
   chmod +x build/simulator-chipyard.harness-QChipRocketConfig
   ```
2. **Stage the toolchain tarball** — once per toolchain refresh; produced
   from validation environment's `toolchain checkout/.toolchain environment/{lib/lib{mpc,mpfr,gmp,z}.so*, riscv-tools/...}`
   with `tar --transform "s,^,qtenon-toolchain/,"` so the archive root is
   `qtenon-toolchain/`. Drop the resulting tarball at
   `build/qtenon-toolchain-amd64.tar.gz`.
3. **Stage the simulator's chipyard-built libs** — `libriscv.so` and
   `libdramsim.so`, stripped on validation environment (`strip --strip-unneeded`), packed as
   `build/qtenon-sim-libs-amd64.tar.gz`.
4. **Build** the Janus4 image from repo root:
   ```bash
   docker build --platform linux/amd64 -t janusq/janus4:isca2026 .
   ```
5. **Smoke test** before pushing:
   ```bash
   bash scripts/smoke_docker.sh
   ```
   During `docker build`, the Qtenon notebook is executed once and its
   compiled ELF, simulator trace/log, and executed notebook are baked into the
   image under `/opt/qtenon-smoke-cache/` and
   `/workspace/2-qtenon/tutorial/runs/hybrid_loop/`. Later smoke runs only
   verify that baked cache instead of re-running the slow notebook. Use
   `--build-arg QTENON_NOTEBOOK_TIMEOUT=...` if the build-time validation
   needs a larger per-cell timeout.
6. **Push** to Docker Hub (requires `docker login` with a credential
   authorized on the `janusq` org):
   ```bash
   docker push janusq/janus4:isca2026
   ```
7. **Pin the digest** — record the resulting `sha256:…` here so attendees
   can pull deterministically: `docker pull janusq/janus4@sha256:<digest>`.

### Published digest

| Tag | Digest | Date |
|---|---|---|
| `janusq/janus4:isca2026` | TBD | TBD |
