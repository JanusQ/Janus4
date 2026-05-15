
# from qiskit.extensions import Initialize
# from qiskit.quantum_info import Statevector
# import numpy as np
# from qiskit import transpile
# # 定义状态向量
# level = 8
# address = np.random.choice(2, 2**level)
# address = address/np.sqrt(sum(address))
# # 创建初始化操作
# init_gate = Initialize(address)

# # 将初始化操作分解为基本门
# decomposed_circuit = init_gate.gates_to_uncompute()
# transpiled_circuit = transpile(decomposed_circuit.inverse(),basis_gates=['u1','h','u3','cz'])
# print(transpiled_circuit)
# exit()





from qiskit_aer import AerSimulator
from qiskit import QuantumCircuit

# Example function to build a noise model
from qram.utils.noisemodel import build_noise_model
# Example quantum circuit
circuit = QuantumCircuit(2,1)

circuit.h(0)
circuit.h(1)
circuit.measure(1,0)
circuit.x(0).c_if(0,0)
circuit.cz(0, 1)
# circuit.measure_all()
circuit.save_density_matrix(qubits=[1], label="rho", conditional=True) # conditional is set to True for considering the measurements
# Build the noise model
noise_bit_flip = build_noise_model()

# Configure the backend with the noise model
backend = AerSimulator(method='density_matrix', device='GPU', noise_model=noise_bit_flip)

# Run the simulation
result = backend.run(circuit).result()

# Extract the density matrix from the result
density_matrix = result.data()['rho']

# Print the density matrix
print("Density Matrix:")
print(density_matrix)
