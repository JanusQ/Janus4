"""Build the AdaptDQC tutorial notebook.

The checked-in notebook is generated from this script so large Markdown and
code cells remain reviewable as plain Python strings.
"""

from __future__ import annotations

import json
from pathlib import Path

_cell_counter = 0


def next_cell_id() -> str:
    global _cell_counter
    _cell_counter += 1
    return f"adaptdqc-{_cell_counter:02d}"


def md(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": next_cell_id(),
        "metadata": {},
        "source": source.strip() + "\n",
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "id": next_cell_id(),
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.strip() + "\n",
    }


cells = [
    md(
        """
# AdaptDQC Tutorial - Circuit Cutting and HybridComm

This notebook is the hands-on companion for the AdaptDQC source tree. It follows
the paper's core flow at a small scale: build a circuit, model the target QPU
capacity, partition the circuit for distributed execution, run the subcircuits,
and reconstruct the final probability distribution.

The paper frames distributed quantum computing through three graphs:

| Paper model | What it captures | Source path used here |
| --- | --- | --- |
| SDHG | spatial qubit relations and wire cuts | `hypridDQC/wireCut/cutter` |
| TDAG | gate order and latency | Qiskit DAG plus `assessment.QPU` metrics |
| CG | chip/subcircuit communication | `complete_path_map` and compute graph |

The notebook intentionally starts with a 3-qubit example and a 2-qubit QPU
capacity so that the full run finishes locally in a few seconds. It then adds a
small HybridComm example that first cuts wires and then compiles a wide
subcircuit with teleportation. It does not reproduce the large benchmark
numbers from the paper; it reproduces the mechanisms that produce a distributed
result.
"""
    ),
    code(
        """
%matplotlib inline

import contextlib
import io
import os
import sys
import warnings
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector


def discover_repo_root(start: Path) -> Path:
    anchor = start.resolve()
    for candidate in (anchor, *anchor.parents):
        if (candidate / "adaptivedqc").is_dir() and (candidate / "benchmark").is_dir():
            return candidate
    raise FileNotFoundError("Could not locate the adaptiveQC repository root.")


repo_root = discover_repo_root(Path.cwd())
os.chdir(repo_root)
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*")

from adaptivedqc.assessment import QPU
from adaptivedqc.assignQubit.compile import Partcompile
from adaptivedqc.hypridDQC.wireCut import CutWire
from adaptivedqc.hypridDQC.wireCut.cutter.post_process import (
    generate_compute_graph,
    generate_subcircuit_entries,
)
from adaptivedqc.hypridDQC.wireCut.excute.tools import quasi_to_real


def format_table(headers, rows):
    rows = [[str(item) for item in row] for row in rows]
    widths = [
        max(len(str(header)), *(len(row[idx]) for row in rows)) if rows else len(str(header))
        for idx, header in enumerate(headers)
    ]
    header = " | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(headers))
    rule = "-+-".join("-" * width for width in widths)
    body = [" | ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)) for row in rows]
    return "\\n".join([header, rule, *body])


qpu = QPU(width=2)
backend_config = qpu.backend.configuration()

print(
    format_table(
        ["item", "value"],
        [
            ["repo", str(repo_root)],
            ["backend", qpu.backend.name()],
            ["QPU width used in tutorial", qpu.width],
            ["backend basis gates", ", ".join(qpu.basis_gates)],
            ["backend coupling edges", len(backend_config.coupling_map)],
        ],
    )
)
"""
    ),
    md(
        """
## 1. Build A Hardware-Compatible Circuit

`CutWire` evaluates latency and error using the backend properties in `QPU`.
For this tutorial we build directly in the `FakeBelem` basis gates
(`sx`, `rz`, `cx`) and use coupling edges that exist on that backend:
`0 -> 1` and `1 -> 2`.

The first qubit is put into a superposition with `sx`; two CNOTs then create a
GHZ-like dependency chain. With a QPU width of 2, the 3-qubit circuit cannot be
placed on one chip, so the cutting pass has real work to do.
"""
    ),
    code(
        """
circuit = QuantumCircuit(3, name="tutorial_ghz_like")
circuit.sx(0)
circuit.rz(0.4, 0)
circuit.cx(0, 1)
circuit.rz(0.3, 1)
circuit.cx(1, 2)
circuit.rz(0.2, 2)

print(circuit.draw(output="text"))
print()
print(
    format_table(
        ["metric", "value"],
        [
            ["qubits", circuit.num_qubits],
            ["depth", circuit.depth()],
            ["operations", dict(circuit.count_ops())],
            ["two-qubit gates", circuit.num_nonlocal_gates()],
            ["unitary factors", circuit.num_unitary_factors()],
        ],
    )
)
"""
    ),
    md(
        """
Before cutting, we compute the exact full-circuit statevector distribution. This
is the reference used at the end of the notebook to verify that the distributed
subcircuit execution reconstructs the same result.
"""
    ),
    code(
        """
full_prob = Statevector.from_instruction(circuit).probabilities()
state_labels = [format(i, f"0{circuit.num_qubits}b") for i in range(2 ** circuit.num_qubits)]

print(
    format_table(
        ["state", "P_full"],
        [[label, f"{prob:.6f}"] for label, prob in zip(state_labels, full_prob)],
    )
)
"""
    ),
    md(
        """
## 2. Cut The Circuit Into QPU-Sized Subcircuits

`CutWire` implements the QubitComm path. It clusters the circuit DAG into
subcircuits whose width is at most the target QPU width. A wire that crosses two
subcircuits becomes a cut edge in `complete_path_map`, which later becomes an
edge in the compute graph used for classical reconstruction.
"""
    ),
    code(
        """
partition_cutter = CutWire(
    circuit,
    name="tutorial_partition",
    qpu=qpu,
    verbose=False,
    data_folder="./data/tutorial_partition",
)

cluster_stdout = io.StringIO()
with contextlib.redirect_stdout(cluster_stdout):
    solution = partition_cutter.cluster_cut()

print("Cluster pass log:")
print(cluster_stdout.getvalue().strip())
print()

summary_rows = []
for subcircuit_idx, subcircuit in enumerate(solution.subcircuits):
    counter = solution.counter[subcircuit_idx]
    summary_rows.append(
        [
            subcircuit_idx,
            subcircuit.num_qubits,
            subcircuit.depth(),
            subcircuit.size(),
            counter["rho"],
            counter["O"],
            counter["effective"],
            dict(subcircuit.count_ops()),
        ]
    )

print(
    format_table(
        ["subcircuit", "width", "depth", "size", "rho", "O", "effective", "ops"],
        summary_rows,
    )
)
print()
print(f"wire cuts: {solution.num_cuts}")
"""
    ),
    code(
        """
def q_label(qubit):
    return f"q{circuit.qubits.index(qubit)}"


path_rows = []
for qubit, path in solution.complete_path_map.items():
    path_rows.append(
        [
            q_label(qubit),
            " -> ".join(
                f"S{item['subcircuit_idx']}:{q_label(item['subcircuit_qubit'])}"
                for item in path
            ),
            "yes" if len(path) > 1 else "no",
        ]
    )

print(format_table(["original wire", "subcircuit path", "cut?"], path_rows))
print()

for subcircuit_idx, subcircuit in enumerate(solution.subcircuits):
    print(f"Subcircuit {subcircuit_idx}")
    print(subcircuit.draw(output="text"))
    print()
"""
    ),
    md(
        """
## 3. Inspect The Compute Graph

In the paper's language, the clustered subcircuits form the chip-level graph
(CG). For every cut wire, AdaptDQC evaluates combinations of `I`, `X`, `Y`, and
`Z` bases. Those entries expand into physical subcircuit instances with concrete
initialization and measurement settings.
"""
    ),
    code(
        """
compute_graph = generate_compute_graph(
    counter=solution.counter,
    subcircuits=solution.subcircuits,
    complete_path_map=solution.complete_path_map,
)
subcircuit_entries, subcircuit_instances = generate_subcircuit_entries(compute_graph)

edge_rows = []
for edge_idx, (src, dst, attrs) in enumerate(compute_graph.edges):
    edge_rows.append(
        [
            edge_idx,
            f"S{src} -> S{dst}",
            q_label(attrs["O_qubit"]),
            q_label(attrs["rho_qubit"]),
            "QubitComm",
        ]
    )

entry_rows = []
for subcircuit_idx in sorted(subcircuit_entries):
    entry_rows.append(
        [
            subcircuit_idx,
            len(subcircuit_entries[subcircuit_idx]),
            len(subcircuit_instances[subcircuit_idx]),
        ]
    )

print("Compute graph edges")
print(format_table(["edge", "path", "O qubit", "rho qubit", "ICC"], edge_rows))
print()
print("Subcircuit execution workload")
print(format_table(["subcircuit", "basis entries", "physical instances"], entry_rows))
"""
    ),
    md(
        """
## 4. Run The Cut Circuit And Reconstruct The Result

The execution cell below runs every subcircuit instance with local statevector
simulation (`eval_mode="sv"`), attributes the measured probabilities to the
compute-graph entries, and contracts them back into one distribution. This is
the end-to-end QubitComm path: quantum subproblem execution plus classical
probability reconstruction.
"""
    ),
    code(
        """
run_cutter = CutWire(
    circuit,
    name="tutorial_run",
    qpu=qpu,
    verbose=False,
    data_folder="./data/tutorial_run",
)

run_stdout = io.StringIO()
with contextlib.redirect_stdout(run_stdout):
    run_solution = run_cutter.run_cut_circuit(eval_mode="sv", recursion_depth=2)

interesting_log = []
for line in run_stdout.getvalue().splitlines():
    if line.startswith("run_subcircuits took") or line.startswith("Cut:") or line.startswith("spend time"):
        interesting_log.append(line)

print("\\n".join(interesting_log))
print()

reconstructed_quasi = run_solution.approximation_bins[0]["bins"]
reconstructed_prob = quasi_to_real(reconstructed_quasi, mode="nearest")
abs_delta = np.abs(reconstructed_prob - full_prob)

result_rows = []
for label, full, reconstructed, delta in zip(
    state_labels,
    full_prob,
    reconstructed_prob,
    abs_delta,
):
    result_rows.append([label, f"{full:.6f}", f"{reconstructed:.6f}", f"{delta:.2e}"])

print(format_table(["state", "full circuit", "cut reconstruction", "abs delta"], result_rows))
print()
print(f"L1 error: {float(abs_delta.sum()):.3e}")
"""
    ),
    code(
        """
time_rows = []
for key, value in run_cutter.times.items():
    if isinstance(value, list):
        rendered = "[" + ", ".join(f"{item:.4f}" for item in value) + "]"
    else:
        rendered = f"{value:.6f}"
    time_rows.append([key, rendered])

print(format_table(["stage", "seconds"], time_rows))
"""
    ),
    md(
        """
## 5. GateComm View: Remote Gate Compilation

The same source tree also contains the GateComm path in `assignQubit`. The next
cell fixes a simple allocation by hand: qubits 0 and 1 live on QPU 0, while
qubit 2 lives on QPU 1. The second CNOT is therefore remote and the compiler
marks an EPR pair before lowering it to a teleportation-style circuit.

This section isolates the GateComm mechanism: a remote gate is made executable
by inserting entanglement resources.
"""
    ),
    code(
        """
allocation = [0, 0, 1]
gate_compiler = Partcompile(circuit, allocation)
epr_num, epr_circuit = gate_compiler.get_epr_circuit()
teleportation_circuit = gate_compiler.compile_with_teleportion()

print(
    format_table(
        ["item", "value"],
        [
            ["allocation", allocation],
            ["EPR pairs", epr_num],
            ["EPR-marked ops", dict(epr_circuit.count_ops())],
            ["teleportation qubits", teleportation_circuit.num_qubits],
            ["teleportation clbits", teleportation_circuit.num_clbits],
            ["teleportation depth", teleportation_circuit.depth()],
            ["teleportation ops", dict(teleportation_circuit.count_ops())],
        ],
    )
)
print()
print(epr_circuit.draw(output="text"))
"""
    ),
    md(
        """
## 6. Adaptive Goal Selection

AdaptDQC is adaptive because the compiler can evaluate more than one candidate
distributed plan and select according to the user's objective. This cell keeps
the search space tiny and explicit: three valid 2-chip allocations for one
4-qubit circuit. The communication objective minimizes EPR pairs first; the
latency objective minimizes the compiled teleportation depth first.

The same candidates are evaluated under both goals, but the selected allocation
is different.
"""
    ),
    code(
        """
adaptive_circuit = QuantumCircuit(4, name="adaptive_goal_demo")
adaptive_circuit.sx(0)
adaptive_circuit.rz(0.1, 0)
adaptive_circuit.cx(1, 2)
adaptive_circuit.rz(0.2, 2)
adaptive_circuit.cx(1, 3)
adaptive_circuit.rz(0.3, 3)
adaptive_circuit.cx(3, 1)
adaptive_circuit.rz(0.4, 1)
adaptive_circuit.cx(1, 2)
adaptive_circuit.rz(0.5, 2)
adaptive_circuit.cx(1, 2)
adaptive_circuit.rz(0.6, 2)

candidate_allocations = [
    [0, 1, 0, 1],
    [0, 1, 1, 0],
    [0, 0, 1, 1],
]


def evaluate_gatecomm_plan(source_circuit, allocation):
    compiler = Partcompile(source_circuit, allocation)
    epr_pairs, marked_circuit = compiler.get_epr_circuit()
    compiled_circuit = compiler.compile_with_teleportion()
    return {
        "allocation": allocation,
        "epr_pairs": float(epr_pairs),
        "compiled_depth": compiled_circuit.depth(),
        "compiled_qubits": compiled_circuit.num_qubits,
        "compiled_ops": dict(compiled_circuit.count_ops()),
    }


plans = [evaluate_gatecomm_plan(adaptive_circuit, allocation) for allocation in candidate_allocations]

communication_choice = min(
    plans,
    key=lambda plan: (plan["epr_pairs"], candidate_allocations.index(plan["allocation"])),
)
latency_choice = min(
    plans,
    key=lambda plan: (plan["compiled_depth"], plan["epr_pairs"]),
)

plan_rows = []
for plan in plans:
    plan_rows.append(
        [
            plan["allocation"],
            plan["epr_pairs"],
            plan["compiled_depth"],
            plan["compiled_qubits"],
            "communication" if plan is communication_choice else "",
            "latency" if plan is latency_choice else "",
        ]
    )

print(format_table(
    ["allocation", "EPR pairs", "compiled depth", "compiled qubits", "chosen by comm.", "chosen by latency"],
    plan_rows,
))
print()
print(f"communication objective -> {communication_choice['allocation']}")
print(f"latency objective       -> {latency_choice['allocation']}")
"""
    ),
    md(
        """
## 7. HybridComm: Wire Cut First, EPR Compile Inside A Wide Subcircuit

The paper's hybrid architecture combines both mechanisms. A practical way to see
that in the source tree is a two-stage flow:

1. use QubitComm / `CutWire` to split a circuit into medium-size subcircuits;
2. use GateComm / `Partcompile` when one of those subcircuits is still wider
   than the physical chip size.

The example below uses a 4-qubit circuit. The wire-cut stage is allowed to keep
up to 3 qubits per subcircuit, while the physical GateComm stage assumes 2-qubit
chips. That creates one QubitComm cut and one GateComm compilation inside the
wider subcircuit.
"""
    ),
    code(
        """
hybrid_circuit = QuantumCircuit(4, name="hybrid_demo")
hybrid_circuit.sx(0)
hybrid_circuit.rz(0.2, 0)
hybrid_circuit.cx(0, 1)
hybrid_circuit.rz(0.3, 1)
hybrid_circuit.cx(1, 2)
hybrid_circuit.rz(0.4, 2)
hybrid_circuit.cx(1, 3)
hybrid_circuit.rz(0.5, 3)

wire_stage_qpu = QPU(width=3)
physical_chip_width = 2

hybrid_cutter = CutWire(
    hybrid_circuit,
    name="hybrid_wire_stage",
    qpu=wire_stage_qpu,
    verbose=False,
    data_folder="./data/tutorial_hybrid",
)

hybrid_stdout = io.StringIO()
with contextlib.redirect_stdout(hybrid_stdout):
    hybrid_solution = hybrid_cutter.cluster_cut()

wire_rows = []
for subcircuit_idx, subcircuit in enumerate(hybrid_solution.subcircuits):
    wire_rows.append(
        [
            subcircuit_idx,
            subcircuit.num_qubits,
            subcircuit.depth(),
            subcircuit.size(),
            dict(subcircuit.count_ops()),
            "needs GateComm" if subcircuit.num_qubits > physical_chip_width else "fits one chip",
        ]
    )

print("Wire-cut stage")
print(hybrid_stdout.getvalue().strip())
print(
    format_table(
        ["subcircuit", "width", "depth", "size", "ops", "next step"],
        wire_rows,
    )
)
print(f"QubitComm wire cuts: {hybrid_solution.num_cuts}")
print()

hybrid_compile_rows = []
for subcircuit_idx, subcircuit in enumerate(hybrid_solution.subcircuits):
    if subcircuit.num_qubits <= physical_chip_width:
        hybrid_compile_rows.append(
            [
                subcircuit_idx,
                "local",
                "-",
                0,
                subcircuit.num_qubits,
                subcircuit.depth(),
                dict(subcircuit.count_ops()),
            ]
        )
        continue

    allocation = [qubit_idx // physical_chip_width for qubit_idx in range(subcircuit.num_qubits)]
    compiler = Partcompile(subcircuit, allocation)
    epr_pairs, marked_circuit = compiler.get_epr_circuit()
    compiled_circuit = compiler.compile_with_teleportion()
    hybrid_compile_rows.append(
        [
            subcircuit_idx,
            "GateComm",
            allocation,
            epr_pairs,
            compiled_circuit.num_qubits,
            compiled_circuit.depth(),
            dict(compiled_circuit.count_ops()),
        ]
    )

print("GateComm stage for wide subcircuits")
print(
    format_table(
        ["subcircuit", "mode", "allocation", "EPR pairs", "compiled qubits", "compiled depth", "compiled ops"],
        hybrid_compile_rows,
    )
)
"""
    ),
    md(
        """
## What This Notebook Demonstrated

1. A small circuit can be built directly in the backend basis used by AdaptDQC's
   quantitative model.
2. `CutWire` partitions the circuit into QPU-sized subcircuits and records the
   cut wire in `complete_path_map`.
3. The compute graph turns a cut into basis-entry workloads over `I`, `X`, `Y`,
   and `Z`.
4. Local subcircuit execution plus classical contraction reconstructs the same
   probability distribution as the full statevector simulation.
5. The GateComm compiler path exposes the EPR-pair cost for a manual remote-gate
   allocation.
6. The adaptive objective example selects different allocations under
   communication and latency goals.
7. The HybridComm example composes both paths: QubitComm between subcircuits and
   GateComm inside a subcircuit that remains wider than the physical chip.

The example is deliberately small, but it exercises the same source-code path
used by larger AdaptDQC experiments.
"""
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python (adaptiveqc)",
            "language": "python",
            "name": "adaptiveqc",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.10",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def main() -> None:
    notebook_path = Path(__file__).with_name("adaptdqc_tutorial.ipynb")
    notebook_path.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(notebook_path)


if __name__ == "__main__":
    main()
