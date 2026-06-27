import qiskit 
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit.dagcircuit import DAGCircuit
from qiskit.converters import circuit_to_dag
from qiskit.circuit.library import IGate
from functools import reduce
def convert_to_layered_circuit(circuit):
    """
    Convert a regular quantum circuit to a layered circuit.
    """
    layered_circuit = QuantumCircuit(circuit.num_qubits,circuit.num_clbits)
    dagcircuit = circuit_to_dag(circuit)
    qargs =[]
    for layerdict in dagcircuit.layers():
        layer = list(layerdict['graph'].topological_op_nodes())
        singleq_nodes = [node for node in layer if len(node.qargs)==1]
        if len(singleq_nodes):
            single_qargs = [node.qargs[0] for node in singleq_nodes]
            for node in singleq_nodes:
                layered_circuit.append(node.op,node.qargs)
            for q in circuit.qubits:
                if q not in single_qargs:
                    layered_circuit.append(IGate(),[q])
        twoq_nodes = [node for node in layer if len(node.qargs)==2]
        if len(twoq_nodes)==0:
            continue
        twoq_qargs = []
        for node in twoq_nodes:
            twoq_qargs.extend(node.qargs)
        for node in twoq_nodes:
            layered_circuit.append(node.op,node.qargs)
        for q in circuit.qubits:
            if q not in twoq_qargs:
                
                layered_circuit.append(IGate(),[q])
    
    return layered_circuit

if __name__ == "__main__":
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.h(1)
    circuit.cx(0,1)
    circuit.h(2)
    # circuit.save_density_matrix(qubits=[1], label="rho", conditional=False) # 
    circuit.x(2)
    circuit.cx(1,0)
    circuit.cx(1,2)
    print("___"*20)
    print(circuit.draw())
    # layered_circuit = convert_to_layered_circuit(circuit)
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import XGate
    from qiskit.transpiler import PassManager, InstructionDurations
    from qiskit.transpiler.passes import ALAPSchedule, DynamicalDecoupling
    from qiskit.visualization import timeline_drawer

    # 定义 DD 序列，这里使用 XGate 作为基本脉冲
    dd_sequence = [XGate(), XGate()]

    # 创建 DynamicalDecoupling 实例
    durations = InstructionDurations(
            [("h", None, 50),("cx", [0, 1], 700), ("reset", None, 10),
             ("cx", [1, 2], 200), ("cx", [2, 3], 300),("cx", [1, 0], 700),
             ("x", None, 50), ("measure", None, 1000)]
        )
    pm = PassManager([ALAPSchedule(durations),
                          DynamicalDecoupling(durations, dd_sequence)])
    layered_circuit = pm.run(circuit)

    print(layered_circuit.draw())