from qiskit import QuantumCircuit
from .optimizer import FM_random, simulated_annealing, genetic_algorithm,RawFM
import warnings
from functools import reduce
from .compile import Partcompile
import warnings
from ..assessment import QPU
class PartDQC:
    def __init__(self,circuit: QuantumCircuit, qpu: QPU, fileDir: str = None, verbose: bool = False):
        """Main class to part QC 
        Args:
            circuit (QuantumCircuit): input circuit
            QPU_width (int): the max width of the QPU
        """

        self.circuit = self.compile_circuit(circuit,backend= qpu.backend)
        self.width = self.circuit.width()
        self.depth = self.circuit.depth()
        # self.allow_cycle = allow_cycle
        self.QPU_width = qpu.width
        self.qpu = qpu
        self.cluster_num = round(self.width / self.QPU_width+0.499999999999)
        self.verbose = verbose  # if True , the run info and process will be printted
        self.timer = {}  # store the runtime
        warnings.filterwarnings('ignore')
    def generate_allocation(self,qpu_list=None):
        from functools import reduce
        if qpu_list:
            initialization = [[i]*w for i,w in enumerate(qpu_list)]
            ## 用reduce 函数实现列表的展开
            initialization = reduce(lambda x,y:x+y,initialization)
        else:
            initialization = [[i]*self.QPU_width for i in range(self.cluster_num)]
            initialization = reduce(lambda x, y: x+y, initialization)
        return initialization
    def allocation_qubits(self,optMethod:str='FM',opt_obj:str='DataFlux',qpu_list=None):
        if optMethod == 'FM':
            return FM_random(self.circuit,opt_obj,self.qpu)
        elif optMethod == 'SA':
            return simulated_annealing(self.circuit, opt_obj, self.generate_allocation(qpu_list),self.qpu)
        elif optMethod == 'GA':
            return genetic_algorithm(self.circuit,opt_obj,self.generate_allocation(qpu_list),self.qpu,100,10,0.5,0.2,4)
        elif optMethod == 'DQNN':
            return self.DQNN_allocation()
        elif optMethod == 'RawFM':
            return RawFM(self.circuit,self.QPU_width)
    def distribute_compile(self,allocation):
        partc = Partcompile(self.circuit,allocation)
        eprNum,epr_circuit = partc.get_epr_circuit()
        distribute_circuit = partc.compile_with_teleportion()
        print('EPR num:',eprNum)
        print('circuit depth:',distribute_circuit.depth())
        print('circuit:',epr_circuit)
        return distribute_circuit

    def DQNN_allocation(self):
        pass

    def compile_circuit(self,circuit=None,backend=None):
        """ simplify the circuit by using the qiskit transpiler
        Args:
            circuit (QuantumCircuit, optional): original circuit. Defaults to Self.circuit.
        Returns:
            QuantumCircuit: circuit after simplification
        """
        if circuit == None:
            circuit = self.circuit
        from qiskit.transpiler.passes import Optimize1qGates,Collect2qBlocks
        from qiskit.transpiler import PassManager
        from qiskit.compiler import transpile
        basis_gates = backend.basis_gates if hasattr(backend, "basis_gates") else backend.configuration().basis_gates
        qc_transpiled = transpile(circuit, basis_gates=basis_gates)
        pass_ = PassManager([Optimize1qGates(),Collect2qBlocks()])
        qc_optimized = pass_.run(qc_transpiled)
        # qc_org = self.optimize_circuit(qc_optimized)
        return qc_optimized
    

    def optimize_circuit(self,circuit:QuantumCircuit) -> QuantumCircuit:
        """
        该方法将被弃用
        """
        list_ins = [ins for ins in circuit.data]
        num_gates = len(list_ins)

        def get_move_ins(i):
            ins = list_ins[i]
            gate = [ins.qubits[0].index, ins.qubits[1].index]
            res = []
            for control_flag in [0, 1]:
                used_qubits = []
                move_inses = []
                for j in range(i + 1, len(list_ins)):
                    current_ins = list_ins[j]
                    if len(current_ins.qubits) == 1:
                        used_qubits.append(current_ins.qubits[0].index)
                        continue
                    current_gate = [current_ins.qubits[0].index,
                                    current_ins.qubits[1].index]
                    if gate[control_flag] == current_gate[control_flag] and all(
                            [qubit not in used_qubits for qubit in current_gate]):
                        move_inses.append(j)
                    else:
                        for qubit in current_gate:
                            if qubit not in used_qubits:
                                used_qubits.append(qubit)
                res.append(move_inses)
            final_move_ins = reduce(lambda x, y: x if len(x) > len(y) else y, res)
            a = 1
            for index in final_move_ins:
                move_ins = list_ins.pop(index)
                list_ins.insert(i + a, move_ins)
                a += 1
            return i + len(final_move_ins) + 1

        # 循环
        i = 0
        while i < num_gates:
            # 单门爬
            if len(list_ins[i].qubits) == 1:
                i += 1
                continue
            # 双门开移
            i = get_move_ins(i)

        new_circuit = QuantumCircuit(circuit.num_qubits)
        for ins in list_ins:
            new_circuit.append(ins)
        return new_circuit
