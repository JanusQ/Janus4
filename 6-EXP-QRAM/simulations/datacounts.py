
from qiskit import QuantumCircuit, transpile, QuantumRegister, ClassicalRegister
import numpy as np
from qram.qramtemplate.buckdatacell import Qram,swap_depth,cswap_depth
from qram.config import Config
if __name__ == "__main__":
    with open(f"counts_data.csv","w") as f:
        f.write("level,num_qubits,swap_depth,cswap_depth,cswap_count,swap_count,h_count,x_count\n")
    levels = range(2,20)
    for level in levels:
        # address = [bin(i)[2:].zfill(level) for i in range(2**level)]
        address =np.array([1]*(2**level))
        address = address/np.sqrt(len(address))
        # data = [i / 8 for i in range(8)]
        data = [0]*(2**level)
        address_qregs = QuantumRegister(level, 'address')
        bus_qregs = QuantumRegister(1, 'bus')
        bus_cregs = ClassicalRegister(1, 'bus_classical')
        address_cregs = ClassicalRegister(level, 'address_classical')
        circuit = QuantumCircuit(address_qregs, bus_qregs, address_cregs,bus_cregs)
        circuit.initialize(address,address_qregs[::-1])
        config = Config()
        config.decompose_mode = 'none'
        config.load_bus = False
        qram = Qram(address, data, bandwidth=1,config=config)
        qram(circuit, address_qregs, bus_qregs)
        circuit.measure(bus_qregs,bus_cregs)
        circuit.measure(address_qregs,address_cregs)
        print(circuit.num_qubits)
        # print(circuit)
        # simulator = Aer.get_backend('qasm_simulator')
        # num_shots = 10000
        # result = simulator.run(circuit,shots=num_shots).result()
        # counts = result.get_counts(circuit)
        # print("测量结果：",{k[::-1]:v/num_shots for k,v in counts.items()})
        # transpiled_circuit = transpile(circuit,basis_gates=['x','h','cswap','swap'],optimization_level=3)
        num_qubits = circuit.num_qubits
        swap_d = swap_depth(circuit)
        cswap_d = cswap_depth(circuit)
        op_counts = circuit.count_ops()
        with open(f"counts_data.csv","a") as f:
            f.write(f"{level},{num_qubits},{swap_d},{cswap_d},{op_counts['cswap']},{op_counts['swap']},{op_counts['h']},{op_counts['x']}\n")
            
    # coupling_map = generate_grid_coupling_map(4,5)
    # # plot_coupling_map(coupling_map, 5, 5)
    # print(coupling_map)
    
    # # transpiled_circuit = transpile(circuit,coupling_map=coupling_map,basis_gates=['x','h','cswap','swap','rz','cz'])
    # transpiled_circuit = transpile(circuit,coupling_map=coupling_map,basis_gates=['rx','rz','cz'],routing_method='basic',initial_layout=None,seed_transpiler=42)
    # # print(transpiled_circuit)
    # result = simulator.run(transpiled_circuit).result()
    # counts = result.get_counts(circuit)
    # print(counts)
    # print("cz 深度:",cz_depth(transpiled_circuit))
    
    # print("门数量:",transpiled_circuit.count_ops())
    # print(transpiled_circuit.layout.input_qubit_mapping)
