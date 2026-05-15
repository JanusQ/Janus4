# 从 QASM 文件中读取量子电路
from qiskit import QuantumCircuit
qasm_file_path = 'cswap.qasm'
circuit_from_qasm = QuantumCircuit.from_qasm_file(qasm_file_path)

# 将 circuit_from_qasm 添加到新电路的指定比特上
cir.compose(circuit_from_qasm, qubits=[qi._bits[0] for qi in q], inplace=True)