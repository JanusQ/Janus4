import numpy as np

def fidelity2lambda_depolar(fidelity,num_qubits=1):
    N = 2**num_qubits
    param = (fidelity*N-1)/(N-1)
    return 1-param

def build_noise_model(
        p_reset = 0.0038/6,
        p_meas = 0.0359,
        p_gate_cz = 0.0038,
        p_gate_single = 0.0038/6,
        p_gate_id = 0.0038/6,
        noise_scale = 0.001,
    ):
    noise_scale_factor = noise_scale/0.001
    p_gate_cz *= noise_scale_factor
    p_gate_single  *=  noise_scale_factor
    p_gate_id  *=  noise_scale_factor
    from qiskit_aer.noise import NoiseModel
    from qiskit_aer.noise import ReadoutError
    from qiskit_aer.noise import pauli_error
    from qiskit_aer.noise import depolarizing_error
    
    # 量子错误对象
    error_reset = pauli_error([('X', p_reset), ('I', 1 - p_reset)])
    error_meas = ReadoutError([[1-p_meas,p_meas],[p_meas,1-p_meas]])
    error_gate1 =  depolarizing_error(fidelity2lambda_depolar(1-p_gate_single), 1)
    error_gate_id =  depolarizing_error(fidelity2lambda_depolar(1-p_gate_id), 1)
    error_gate_cz = depolarizing_error(fidelity2lambda_depolar(1-p_gate_cz,num_qubits=2), 2)
    # 添加错误到噪声模型
    noise_bit_flip = NoiseModel(basis_gates=['cz', 'id', 'rx','h','ry','initialize','reset'])
    noise_bit_flip.add_all_qubit_quantum_error(error_gate1, [ 'rx','h','ry','x'])
    noise_bit_flip.add_all_qubit_quantum_error(error_gate_id, [ 'id'])
    noise_bit_flip.add_all_qubit_quantum_error(error_reset, "reset")
    noise_bit_flip.add_all_qubit_readout_error(error_meas)
    noise_bit_flip.add_all_qubit_quantum_error(error_gate_cz, ["cz"])
    return  noise_bit_flip



