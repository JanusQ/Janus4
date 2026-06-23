from math import floor, prod
from typing import Union, Iterable
from ..assessment import QPU
class GateFakeMetric:
    def __init__(self,qpu:QPU=None) -> None:
        if qpu:
            self.qpu = qpu
        else:
            self.qpu = QPU(5)
    
    def latency(self,gatename: str, qubit: Union[int, Iterable[int]]):
        single_latency = self.qpu.latency('x',qubit[0])
        if gatename == 'epr':
            return 10*single_latency*15.3  # 12+2+1+0.1*3
        else:
            # single qubit gate
            return self.qpu.latency(gatename,qubit)
        
    def error(self,gatename: str,qubit: Union[int, Iterable[int]]):
        if gatename == 'epr':
            return self.qpu.measurement_error(qubit)
        else:
            return self.qpu.gate_error(gatename,qubit)


class DQCMetric:
    """Metric for DQC"""
    def __init__(self, complieGraph, width,qpu:QPU) -> None:
        self.width = width
        self.complieGraph = complieGraph
        self.gateMetric = GateFakeMetric(qpu)
    @property
    def _latency(self):
        latency_dict = [0]*self.width
        for gate in self.complieGraph.topological_op_nodes():
            max_latency = max([latency_dict[q._index]
                              for q in gate.qargs])+self.gateMetric.latency(gate.op.name,[q._index for q in gate.qargs])
            for q in gate.qargs:
                latency_dict[q._index] = max_latency
        return latency_dict
    @property
    def Latency(self):
        return max(self._latency)

    @property
    def _fidelity(self):
        fidelity = [1]*self.width
        for gate in self.complieGraph.topological_op_nodes():
            error = self.gateMetric.error(gate.op.name,[q._index for q in gate.qargs])
            for q in gate.qargs:
                fidelity[q._index] *= (1 - error)
        return fidelity
    @property
    def Fidelity(self):
        return prod(self._fidelity)
    @property
    def QU(self):
        gate_latency = [0]*self.width
        for gate in self.complieGraph.topological_op_nodes():
            for q in gate.qargs:
                gate_latency[q._index] += self.gateMetric.latency(gate.op.name,[q._index for q in gate.qargs])
        return sum(gate_latency)/sum(self._latency)
