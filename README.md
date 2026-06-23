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
`qtenon-venv` for Qtenon and `chocoq` for Choco-Q.

## Topics

- **[`2-qtenon/`](2-qtenon/)** — Topic 2: low-latency quantum-classical hybrid control on a RISC-V + RoCC accelerator. Hybrid-loop demo with baked Verilator run artifacts in the Janus4 image.
- **`3-artery/`** — Topic 3 placeholder.
- **[`4-adaptDQC/`](4-adaptDQC/)** — Topic 4: adaptive distributed quantum computing with local Qiskit simulation in the `adaptiveqc` kernel.
- **[`5-Choco-Q/`](5-Choco-Q/)** — Topic 5: constrained binary optimization with Choco-Q in the `chocoq` kernel.
- **`6-EXP-QRAM/`** — Topic 6 placeholder.

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
