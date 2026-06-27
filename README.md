# Janus 4.0

Quantum-classical Heterogeneous Architecture and Flexible Scheduling — framework repository accompanying the **ISCA 2026 tutorial**.

Tutorial landing page: https://janusq.github.io/ISCA_2026_Tutorial/

## Quickstart

```bash
docker pull janusq/janus4:isca2026
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

Open JupyterLab at `http://localhost:8888/lab`. The single Janus4 image
contains the numbered topic tree and topic-specific kernels, including
`qtenon` for Qtenon, `artery` for ARTERY, `adaptiveqc` for AdaptDQC,
`chocoq` for Choco-Q, and `qram` for EXP-QRAM.

### Apple Silicon / ARM Mac

The published tutorial image is currently `linux/amd64` only because the
bundled Qtenon RISC-V toolchain and Verilator simulator artifacts are built for
x86_64 Linux. On Apple Silicon Macs, run the same image through Docker's
cross-architecture emulation layer:

```bash
# Docker Desktop or Colima both work. With Colima:
colima start --cpu 4 --memory 8 --disk 40

docker pull --platform linux/amd64 janusq/janus4:isca2026
docker run --rm \
  --platform linux/amd64 \
  -p 127.0.0.1:8888:8888 \
  janusq/janus4:isca2026
```

Do not switch the command to `--platform linux/arm64`: there is no native ARM
image for this tag. Inside the container, `uname -m` will report `x86_64` even
on an ARM Mac. That is expected. Normal tutorial notebook runs use checked-in
Qtenon replay captures and a baked executed-notebook smoke cache, so the
emulation overhead is modest; opting into fresh Qtenon live simulation with
`QTENON_RUN_LIVE_SIM=1` or `QTENON_RUN_PAPER_EXPERIMENT=1` will be much slower.

## Topics

- **[`2-qtenon/`](2-qtenon/)** — Topic 2: low-latency quantum-classical hybrid control on a RISC-V + RoCC accelerator. Hybrid-loop and paper-figure walkthroughs use checked-in replay captures by default, with a baked notebook smoke cache in the Janus4 image.
- **[`3-adaptDQC/`](3-adaptDQC/)** — Topic 3: adaptive distributed quantum computing with local Qiskit simulation in the `adaptiveqc` kernel.
- **[`4-EXP-QRAM/`](4-EXP-QRAM/)** — Topic 4: bucket-brigade QRAM circuit construction, simulation, and processed data visualization in the `qram` kernel.
- **[`5-artery/`](5-artery/)** — Topic 5: ARTERY-style low-latency quantum feedback with S21/IQ analysis, trajectory prediction, compressed tutorial data in the `artery` kernel, hardware interface notes, and GUI/UDP demos.
- **[`6-Choco-Q/`](6-Choco-Q/)** — Topic 6: constrained binary optimization with Choco-Q in the `chocoq` kernel.

## Adding a new topic

1. Create a new top-level directory using the tutorial number and topic name (e.g. `7-new-topic/`).
2. Include a `README.md`, your source code, and a topic environment recipe or kernel setup that can be folded into the root Dockerfile.
3. Open a pull request against `main`.

The framework-wide tutorial Docker image is built from the root Dockerfile:

```bash
docker build --platform linux/amd64 -t janusq/janus4:isca2026 .
```

## Related repositories

- [`JanusQ/JanusQ`](https://github.com/JanusQ/JanusQ) — Janus 3.0 framework (HPCA 2025 tutorial)
- [`JanusQ/HPCA_2025_Tutorial`](https://github.com/JanusQ/HPCA_2025_Tutorial) — Janus 3.0 tutorial site
- [`JanusQ/ISCA_2026_Tutorial`](https://github.com/JanusQ/ISCA_2026_Tutorial) — Janus 4.0 tutorial landing site (React SPA)

## License

MIT. See [`LICENSE`](LICENSE).
