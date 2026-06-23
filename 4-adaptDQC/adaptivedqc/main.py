
from qiskit import QuantumCircuit
from qiskit.circuit.parameterexpression import ParameterValueType
from typing import Dict, Optional, Sequence, Union
from qiskit.circuit.quantumcircuit import Register, Bit
from .hypridDQC.wireCut import CutWire
from .assessment.qpu import QPU
from .excute import IBMCloudRun
from .assignQubit import PartDQC
class Adaptivedqc(QuantumCircuit):
    def __init__(self,
        *regs: Union[Register, int, Sequence[Bit]],
        name: Optional[str] = None,
        global_phase: ParameterValueType = 0,
        metadata: Optional[Dict] = None) -> None:

        super().__init__(*regs, name=name, global_phase=global_phase, metadata=metadata)
    def run_on_cut_wire(self):
        backend = IBMCloudRun().get_backend('ibmq_belem')
        qpu = QPU(width=int(self.num_qubits*2/3),backend=backend)
        solution = CutWire(self,name='cut_wire',qpu=qpu).run_cut_circuit()
        return solution
    def run_on_cut_gate(self):
        pass
    def run_on_part_qubits(self,width=5,backendname = 'ibmq_belem'):
        backend = IBMCloudRun().get_backend(backendname)
        qpu = QPU(width=width,backend=backend)
        pdqc= PartDQC(self,qpu=qpu)
        allocation = pdqc.allocation_qubits(optMethod='FM',opt_obj='DataFlux')
        print('allocation:',allocation)
        distribute_circuit = pdqc.distribute_compile(allocation)
        return distribute_circuit


