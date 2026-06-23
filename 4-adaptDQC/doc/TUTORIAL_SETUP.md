# AdaptDQC Tutorial Setup

This setup keeps the tutorial reproducible without an IBM Quantum token. The
notebook uses the repository code, Qiskit Aer statevector simulation, and the
default `FakeBelem` backend properties used by `adaptivedqc.assessment.QPU`.

## Environment

From the `4-adaptDQC/` directory:

```bash
uv python install 3.10
uv sync --extra tutorial
uv run python -m ipykernel install --user --name adaptiveqc --display-name "AdaptDQC"
```

The Python range is restricted in `pyproject.toml` to `>=3.10,<3.11` because
this repository pins Qiskit 0.42.0 and Qiskit Terra 0.23.2. The environment also
pins `setuptools<81`, because the pinned Qiskit stack still imports
`pkg_resources`.

## Run The Notebook

Open the notebook:

```bash
uv run jupyter notebook tutorial/adaptdqc_tutorial.ipynb
```

Or execute it headlessly:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace tutorial/adaptdqc_tutorial.ipynb
```

The notebook demonstrates:

- constructing a hardware-compatible three-qubit circuit;
- cutting it into subcircuits with the QubitComm / wire-cut path;
- executing each subcircuit locally with `eval_mode="sv"`;
- reconstructing the final probability distribution and comparing it with the
  full-circuit statevector result;
- briefly compiling the same circuit through the GateComm / teleportation path
  to show the EPR-pair cost;
- selecting different distributed allocations under communication and latency
  optimization goals;
- composing the two mechanisms into a HybridComm example: first wire-cut a
  larger circuit, then use GateComm/EPR compilation for the wider subcircuit.

No IBM Quantum account is required for this tutorial path.
