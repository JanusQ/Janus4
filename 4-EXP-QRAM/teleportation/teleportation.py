from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit_aer import Aer

def two_teleportation(circuit,alice_bit, bell_bits,feedback=True):
    ## prepare the entangled state
    circuit.h(bell_bits[0])
    circuit.cx(bell_bits[0], bell_bits[1])
    ## send the qubit to alice
    circuit.cx(alice_bit, bell_bits[0])
    circuit.barrier()
    circuit.h(alice_bit)
    ## send the qubit to bob
    telemeasureClbits = ClassicalRegister(2, name='teleSClbits')
    circuit.add_register(telemeasureClbits)
    if feedback:
        circuit.measure(alice_bit, telemeasureClbits[0])
        circuit.measure(bell_bits[0], telemeasureClbits[1])
        circuit.z(bell_bits[1]).c_if(telemeasureClbits[0], 1)
        circuit.x(bell_bits[1]).c_if(telemeasureClbits[1], 1)
    else:
        circuit.cz(alice_bit, bell_bits[1])
        circuit.cx(bell_bits[0], bell_bits[1])
        circuit.measure(alice_bit, telemeasureClbits[0])
        circuit.measure(bell_bits[0], telemeasureClbits[1])
    
    circuit.reset(alice_bit)
    circuit.reset(bell_bits[0])
    return bell_bits[1]
def three_teleportation(circuit,alice_bit, graph_bits, feedback=True):
    ## prepare the entangled state
    circuit.h(graph_bits[0])
    circuit.cx(graph_bits[0], graph_bits[1])
    circuit.cx(graph_bits[1], graph_bits[2])
    circuit.barrier(graph_bits)
    ## send the qubit to alice
    circuit.cx(alice_bit, graph_bits[0])
    circuit.h(alice_bit)
    ## send the qubit to bob
    telemeasureClbits = ClassicalRegister(2, name='teleClbits')
    circuit.add_register(telemeasureClbits)
    if feedback:
        circuit.measure(alice_bit, telemeasureClbits[0])
        circuit.measure(graph_bits[0], telemeasureClbits[1])
        circuit.z(graph_bits[2]).c_if(telemeasureClbits[0], 1)
        circuit.x(graph_bits[2]).c_if(telemeasureClbits[1], 1)
    else:
        circuit.cz(alice_bit, graph_bits[2])
        circuit.cx(graph_bits[0], graph_bits[2])
        circuit.measure(alice_bit, telemeasureClbits[0])
        circuit.measure(graph_bits[0], telemeasureClbits[1])
    
    return graph_bits[2]

if __name__ == '__main__':
    # create a quantum circuit with 3 qubits
    circuit = QuantumCircuit()
    # create a quantum register with 3 qubits
    alice_bit = QuantumRegister(1, name='alice_bit')
    # bell_bits = QuantumRegister(2, name='bell_bits')
    graph_bits = QuantumRegister(3, name='graph_bits')
    # add the quantum registers to the circuit
    circuit.add_register(alice_bit)
    # circuit.add_register(bell_bits)
    circuit.add_register(graph_bits)
    # apply the teleportation algorithm
    # bell_bit = two_teleportation(circuit, alice_bit[0], bell_bits)
    # circuit.h(alice_bit)
    graph_bit = three_teleportation(circuit, alice_bit, graph_bits)
    # print the circuit
    print(circuit)
    telebits = ClassicalRegister(1, name='telebits')
    circuit.add_register(telebits)
    circuit.measure(graph_bit, telebits)
    simulator = Aer.get_backend('qasm_simulator')
    result = simulator.run(circuit).result()
    
    counts = result.get_counts(circuit)
    print(counts)

        