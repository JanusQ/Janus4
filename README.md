# Janus 4.0

Quantum-classical Heterogeneous Architecture and Flexible Scheduling — framework repository accompanying the **ISCA 2026 tutorial**.

Tutorial landing page: https://janusq.github.io/ISCA_2026_Tutorial/

## Topics

- **[`qtenon/`](qtenon/)** — Topic 2: low-latency quantum-classical hybrid control on a RISC-V + RoCC accelerator. Hybrid-loop demo with live Verilator simulation. Pull the tutorial image: `docker pull janusq/qtenon:isca2026`.
- _(more Janus 4.0 topics will land here as their authors contribute)_

## Adding a new topic

1. Create a new top-level directory named after your project (e.g. `quct4/`, `morphqpv2/`).
2. Include a `README.md`, your source code, and ideally a `Dockerfile` or environment recipe so attendees can reproduce the demo.
3. Open a pull request against `main`.

The framework-wide tutorial Docker image (`janusq/janus4:isca2026`) will be assembled from these per-topic subtrees once the topic set stabilizes.

## Related repositories

- [`JanusQ/JanusQ`](https://github.com/JanusQ/JanusQ) — Janus 3.0 framework (HPCA 2025 tutorial)
- [`JanusQ/HPCA_2025_Tutorial`](https://github.com/JanusQ/HPCA_2025_Tutorial) — Janus 3.0 tutorial site
- [`JanusQ/ISCA_2026_Tutorial`](https://github.com/JanusQ/ISCA_2026_Tutorial) — Janus 4.0 tutorial landing site (React SPA)

## License

MIT. See [`LICENSE`](LICENSE).
