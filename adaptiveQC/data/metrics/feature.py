from qiskit.circuit import QuantumCircuit
from qiskit.converters import dag_to_circuit,circuit_to_dag
from qiskit.dagcircuit import DAGOpNode
from math import prod
from typing import Union, Iterable


class FakeMetric:
    def __init__(self) -> None:
        pass

    def latency(self, gate: str, qubits: Union[int, Iterable[int]]):
        if len(qubits) == 1:
            return 5e-8
        else:
            return 5e-7

    def measurement_error(self, qubit: Union[int, Iterable[int]] = None):
        return 1e-3

    def latency_dict(self, gate: str, qubits: Union[int, Iterable[int]]):
        lat_dict = {}
        latency = self.latency(gate, qubits)
        for q in qubits:
            lat_dict[q] = latency
        return lat_dict

    def gate_error(self, gate: str, qubit: Union[int, Iterable[int]]):
        if len(qubit) == 1:
            return 1e-5
        else:
            return 1e-4

    def error_dict(self, gate: str, qubits: Union[int, Iterable[int]]):
        err_dict = {}
        err = self.gate_error(gate, qubits)
        for q in qubits:
            err_dict[q] = err
        return err_dict

class Circuitfeature:
    def __init__(self,circuit:QuantumCircuit) -> None:
        self._circuit = circuit
        self._dagcircuit = circuit_to_dag(circuit)
        self._qargs = circuit.qubits
        self._metric = FakeMetric()
        self.width = self.width()
        self.depth = self.depth()
        self.two_qubit_gate_num = self.two_qubit_gate_num()
        self.one_qubit_gate_num = self.one_qubit_gate_num()
        self.size = self.size()
        self.qubit_utilizztion = self.qubit_utilizztion()
        self.fidelity = self.fidelity()
        self.latency_all = self.latency_all()

    
    def width(self):
        return self._circuit.width()
    
    def depth(self):
        return self._circuit.depth()
    @property
    def two_qubit_gates(self):
        return [node.op for node in self._dagcircuit._multi_graph.nodes() if isinstance(node, DAGOpNode) and len(node.qargs)==2]
    @property
    def one_qubit_gates(self):
        return [node.op for node in self._dagcircuit._multi_graph.nodes() if isinstance(node, DAGOpNode) and len(node.qargs)==1]
    
    def two_qubit_gate_num(self):
        return len(self.two_qubit_gates)
    
    def one_qubit_gate_num(self):
        return len(self.one_qubit_gates)
    
    def size(self):
        return self._circuit.size()
    
    def qubit_utilizztion(self):
        ### caculate the latency  of whole circuits
        gate_latency ={}
        for q in self._qargs:
            gate_latency[q] = 0
        for gate in self._dagcircuit.topological_op_nodes():
            q_indexes = [q._index for q in gate.qargs]
            for q in gate.qargs:
                gate_latency[q] += self._metric.latency(gate.op.name,q_indexes)
        return sum(gate_latency.values())/sum(self._latency.values())
    @property
    def _error(self):
        error_dict = {}
        for q in self._qargs:
            error_dict[q] = 0
        for gate in self._dagcircuit.topological_op_nodes():
            q_indexes = [q._index for q in gate.qargs]
            error = self._metric.gate_error(gate.op.name,q_indexes)
            for q in gate.qargs:
                error_dict[q]+= error
        return error_dict
    def fidelity(self):
        return prod([1-e for e in self._error.values()])
    @property
    def _latency(self):
        latency_dict = {}
        for q in self._qargs:
            latency_dict[q] = 0
        for gate in self._dagcircuit.topological_op_nodes():
            q_indexes = [q._index for q in gate.qargs]
            max_latency = max([latency_dict[q] for q in gate.qargs])+self._metric.latency(gate.op.name,q_indexes)
            for q in gate.qargs:
                latency_dict[q] = max_latency
        return latency_dict
    
    def latency_all(self):
        return max(self._latency.values())
    

