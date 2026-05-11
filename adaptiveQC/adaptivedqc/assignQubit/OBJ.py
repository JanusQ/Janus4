from .Metric import DQCMetric
from qiskit import QuantumCircuit
from typing import Iterable
import networkx as nx
from qiskit.converters import circuit_to_dag
import numpy as np
from ..assessment import QPU
from .compile import Partcompile
def dag_similarity(G1, G2):
    # Calculate the GED between G1 and G2
    ged = nx.graph_edit_distance(G1, G2)
    # Calculate the similarity metric as the inverse of the normalized GED
    sim_metric = 1- ged / (len(G1.nodes) + len(G2.nodes))
    return sim_metric

class DQCObj:
    def __init__(self, circuit: QuantumCircuit, allocation: Iterable,qpu:QPU) -> None:
        """ Init the DQCObj

        Args:
            circuit (QuantumCircuit):  QuantumCircuit
            allocation (Iterable):  the allocation of the qubits the format is like [0,0,1,1,2,2,3,3],
            the first two qubits are allocated to the first QPU, the second two qubits are allocated to the second QPU, and so on.
        """
        self.circuit = circuit
        self.width = circuit.width()
        self.qpu = qpu
        self.allocation = allocation
        self.chipNum = max(allocation)+1
        self.chipQubits = self.chip_qubits()
        eprs,new_circuit = Partcompile(circuit,allocation).get_epr_circuit()
        self.epr_dag = circuit_to_dag(new_circuit)
        self.epr_num = eprs
        self.metric = DQCMetric(self.epr_dag, self.width,qpu)

    def chip_qubits(self):
        chipQubits  = [[] for _ in range(self.chipNum)]
        for idx,chip in enumerate(self.allocation):
            chipQubits[chip].append(idx)
        return chipQubits
    def DataFlux(self):
        return self.epr_num
    def Latency(self):
        return self.metric.Latency

    def Fidelity(self):
        return self.metric.Fidelity
    def TopologySim(self)->float:
        self.get_sub_Graph()
        return np.prod([self.adj_sim(m,self.qpu.adj) for m in self.subGraphs])
    def Topology(self,a=1,b=2):
        return a*self.TopologySim()+b*self.epr_num/self.circuit.num_nonlocal_gates()
    def adj_sim(self,adj1,adj2):
        G1 = nx.from_numpy_array(adj1)
        G2 = nx.from_numpy_array(adj2)
        return dag_similarity(G1, G2)
    def get_sub_Graph(self):
        ## a adj matrix, M[i][j] means i control j
        self.subGraphs = []
        self.vector = self.circuit_to_vector(self.circuit)
        self.QPUWidths = [self.qpu.width for _ in range(self.chipNum)]
        for chip,width in enumerate(self.QPUWidths):
            M = np.zeros((width,width))
            for idx,qidx in enumerate(self.chipQubits[chip]):
                for jdx,qjdx in enumerate(self.chipQubits[chip]):
                    M[idx][jdx]= self.vector[qidx, qjdx]
            self.subGraphs.append(M)
    def circuit_to_vector(self,circuit:QuantumCircuit):
        """Encodes a directed acyclic graph into a vector using the specified encoding scheme."""
        num_qubits = circuit.width()
        vector = np.zeros((num_qubits, num_qubits))
        for edge in circuit.data:
            if edge.operation.num_qubits==2:
                control_qubit = edge.qubits[0]._index
                target_qubit = edge.qubits[1]._index
                vector[control_qubit, target_qubit] = 1
        return vector
    
    def get_obj_value(self,opt_obj):
        if opt_obj == 'DataFlux':
            return self.DataFlux()
        elif opt_obj == 'Latency':
            return self.Latency()
        elif opt_obj == 'Fidelity':
            return self.Fidelity()
        elif opt_obj == 'Topology':
            return self.TopologySim()
        else:
            raise ValueError('optimize must be DataFlux,Latency,Fidelity or QU')
    def get_obj_min(self,opt_obj):
        if opt_obj == 'DataFlux':
            return self.DataFlux()
        elif opt_obj == 'Latency':
            return self.Latency()
        elif opt_obj == 'Fidelity':
            return 1- self.Fidelity()
        elif opt_obj == 'Topology':
            return self.Topology()
        else:
            raise ValueError('optimize must be DataFlux,Latency,Fidelity or QU')