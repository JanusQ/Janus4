# Choco-Q

Topic 5 of the Janus 4.0 tutorial imports the Choco-Q constrained binary optimization demo from JanusQ.

## Layout

- `chocoq/` contains the runnable Python package.
- `tutorial/6_1_constrained_binary_optimization.ipynb` is the attendee-facing notebook.
- `examples/data/chocoq_examples/` contains the evaluation and visualization examples used by the notebook references.
- `examples/picture/` contains notebook figures.

## Docker

Choco-Q runs inside the shared Janus4 tutorial image:

```bash
docker pull janusq/janus4:isca2026
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

Then open `5-Choco-Q/tutorial/6_1_constrained_binary_optimization.ipynb`
and select the `Choco-Q` kernel. The image uses `gurobipy==13.0.2`, whose
pip-bundled restricted license is enough for this small tutorial model.

For a quick import and notebook execution check:

```bash
5-Choco-Q/scripts/smoke_docker.sh
```
