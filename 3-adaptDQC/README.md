# AdaptDQC Tutorial

This repository contains the artifact code for **AdaptDQC: Adaptive Distributed
Quantum Computing With Quantitative Performance Analysis**. The tutorial path in
this repository is intentionally small and reproducible: it demonstrates the
compiler mechanisms from the paper without requiring an IBM Quantum account.

The main entry point is:

- [`tutorial/adaptdqc_tutorial.ipynb`](tutorial/adaptdqc_tutorial.ipynb)

The notebook follows the paper's core workflow:

1. build a hardware-compatible quantum circuit;
2. model a target QPU capacity with backend latency and error metrics;
3. cut the circuit into distributed subcircuits with QubitComm / wire cutting;
4. execute subcircuit instances locally and reconstruct the final probability
   distribution;
5. compile remote gates with GateComm / EPR teleportation;
6. show adaptive goal selection by choosing different allocations under
   communication and latency objectives;
7. compose QubitComm and GateComm in a small HybridComm example.

## Docker

AdaptDQC runs inside the shared Janus4 tutorial image:

```bash
docker pull janusq/janus4:isca2026
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

Then open `3-adaptDQC/tutorial/adaptdqc_tutorial.ipynb` and select the
`AdaptDQC` kernel.

For a quick import and notebook execution check:

```bash
3-adaptDQC/scripts/smoke_docker.sh
```

## Local Environment

The project uses `pyproject.toml` and `uv.lock`. Python is restricted to
`>=3.10,<3.11` because the code pins Qiskit 0.42.0 / Qiskit Terra 0.23.2.

From this directory:

```bash
uv python install 3.10
uv sync --extra tutorial
uv run python -m ipykernel install --user --name adaptiveqc --display-name "AdaptDQC"
```

Run the notebook headlessly:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace tutorial/adaptdqc_tutorial.ipynb
```

Or open it interactively:

```bash
uv run jupyter notebook tutorial/adaptdqc_tutorial.ipynb
```

No IBM Quantum token is needed for the tutorial. It uses local Qiskit
statevector simulation and the default `FakeBelem` backend properties used by
`adaptivedqc.assessment.QPU`.

## Source Map

| Path | Role in the tutorial |
| --- | --- |
| `adaptivedqc/assessment/` | QPU, backend latency, error, topology metrics |
| `adaptivedqc/hypridDQC/wireCut/` | QubitComm / wire-cut partitioning, subcircuit execution, reconstruction |
| `adaptivedqc/assignQubit/` | GateComm allocation and teleportation-style EPR compilation |
| `benchmark/` | Marker and notes for omitted MQTBench-derived benchmark QASM files used by larger experiments |
| `doc/TUTORIAL_SETUP.md` | setup notes for the notebook environment |
| `tutorial/build_notebook.py` | reproducible notebook generator |

## Paper Concepts Covered

| Paper concept | Tutorial demonstration |
| --- | --- |
| SDHG | qubit-wire dependencies and `complete_path_map` from `CutWire` |
| TDAG | Qiskit DAG clustering with latency/error-aware `QPU` metrics |
| CG | subcircuit compute graph and inter-subcircuit cut edges |
| QubitComm | wire cuts, basis expansion, and probability reconstruction |
| GateComm | remote-gate allocation and EPR-pair insertion |
| HybridComm | wire-cut first, then EPR-compile a still-wide subcircuit |
| Adaptive objectives | communication-oriented vs latency-oriented allocation choices |

## Minimal API Examples

QubitComm / wire cut:

```python
from qiskit import QuantumCircuit
from adaptivedqc.assessment import QPU
from adaptivedqc.hypridDQC.wireCut import CutWire

circuit = QuantumCircuit(3)
circuit.sx(0)
circuit.rz(0.4, 0)
circuit.cx(0, 1)
circuit.rz(0.3, 1)
circuit.cx(1, 2)
circuit.rz(0.2, 2)

qpu = QPU(width=2)
solution = CutWire(circuit, name="wire_demo", qpu=qpu).run_cut_circuit(
    eval_mode="sv",
    recursion_depth=2,
)
print(solution.num_cuts, len(solution.subcircuits))
```

GateComm / EPR compilation:

```python
from adaptivedqc.assignQubit.compile import Partcompile

allocation = [0, 0, 1]
compiler = Partcompile(circuit, allocation)
epr_pairs, epr_marked_circuit = compiler.get_epr_circuit()
teleportation_circuit = compiler.compile_with_teleportion()
print(epr_pairs, teleportation_circuit.depth())
```

Adaptive objective selection:

```python
candidate_allocations = [[0, 1, 0, 1], [0, 1, 1, 0], [0, 0, 1, 1]]
# See tutorial/adaptdqc_tutorial.ipynb for a complete table that selects
# different allocations for communication and latency goals.
```

## Notes

- The tutorial is a mechanism-level reproduction, not a full benchmark
  reproduction of the paper's large-scale figures.
- The historical `data/` cache is not included in Janus4 because the tutorial
  notebook does not read it; it creates `data/tutorial_*` runtime outputs when
  executed.
- The package directory is named `adaptivedqc`; the repository and paper use the
  project name AdaptDQC.
- The historical spelling `hypridDQC` and `compile_with_teleportion` is kept to
  match the existing source tree.
