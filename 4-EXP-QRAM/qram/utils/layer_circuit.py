import qiskit 
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit.dagcircuit import DAGCircuit,DAGInNode,DAGOutNode
from qiskit.converters import circuit_to_dag
from qiskit.circuit.library import IGate
from functools import reduce
def convert_to_layered_circuit(circuit):
    """
    Convert a regular quantum circuit to a layered circuit.
    """
    layered_circuit = circuit.copy()
    layered_circuit.data.clear()
    dagcircuit = circuit_to_dag(circuit)
    
    for layerdict in dagcircuit.layers():
        rawlayer = list(layerdict['graph'].topological_nodes())
        layer = []
        for node in rawlayer:
            if isinstance(node,DAGInNode) or isinstance(node,DAGOutNode):
                continue
            else:
                layer.append(node)
        singleq_nodes = [node for node in layer if len(node.qargs)==1]
        if len(singleq_nodes):
            single_qargs = [node.qargs[0] for node in singleq_nodes]
            for node in singleq_nodes:
                layered_circuit.append(node.op,node.qargs)
            for q in circuit.qubits:
                if q not in single_qargs:
                    layered_circuit.append(IGate(duration=singleq_nodes[0].op.duration),[q])
        twoq_nodes = [node for node in layer if len(node.qargs)==2]
        layered_circuit.barrier()
        if len(twoq_nodes)==0:
            continue
        twoq_qargs = []
        for node in twoq_nodes:
            twoq_qargs.extend(node.qargs)
        for node in twoq_nodes:
            layered_circuit.append(node.op,node.qargs)
        for q in circuit.qubits:
            if q not in twoq_qargs:
                layered_circuit.append(IGate(duration=twoq_nodes[0].op.duration),[q])
        layered_circuit.barrier()
        other_nodes = [node for node in layer if len(node.qargs)>2]
        if len(other_nodes):
            print(other_nodes)
        for node in other_nodes:
            layered_circuit.append(node.op,node.qargs)
    return layered_circuit