
from qiskit import QuantumCircuit, transpile, QuantumRegister, ClassicalRegister
import numpy as np
from qram.qramtemplate.buckdatacell import Qram,swap_depth,cswap_depth
from qram.utils.noisemodel import build_noise_model
from qiskit.quantum_info import state_fidelity
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qram.utils.layer_circuit import convert_to_layered_circuit
import ray
import pickle
import os

from qram.config import Config
def get_densitymatrix(circuit,noise= False):
    if noise:
        noise_bit_flip = build_noise_model()
        backend = AerSimulator(method='tensor_network',device='GPU',
                                noise_model=noise_bit_flip)
        result = backend.run(circuit).result()
    else:
        backend = AerSimulator(method='tensor_network',device='GPU',)
        result = backend.run(circuit).result()
    
    return result.data()['rho']

def generate_sparse_state(circuit,addressqregs,sparse_num=1):
    h_number = np.log2(sparse_num)
    if sparse_num == 1:
        for idx in range(len(addressqregs)):
            if np.random.rand() > 0.5:
                circuit.x(addressqregs[idx])
                
    elif abs(h_number-int(h_number))<1e-4:
        h_qubits = np.random.choice(addressqregs,int(np.log2(sparse_num)),replace=False)
        for q in h_qubits:
            circuit.h(q)
        for idx in range(len(h_qubits)-1):
            circuit.h(h_qubits[idx+1])
            circuit.cz(h_qubits[idx],h_qubits[idx+1])
            circuit.h(h_qubits[idx+1])
    # circuit = convert_to_layered_circuit(circuit)
    # print(circuit.draw())
    
# @ray.remote(num_gpus=1/2)
def test_fidelity(i):
    data = np.random.choice(2,2**level)
    # data = [0]*(2**level)
    address_qregs = QuantumRegister(level, 'address')
    bus_qregs = QuantumRegister(1, 'bus')
    bus_cregs = ClassicalRegister(1, 'bus_classical')
    address_cregs = ClassicalRegister(level, 'address_classical')
    precircuit = QuantumCircuit(address_qregs, bus_qregs, address_cregs,bus_cregs)
    # circuit.h(address_qregs[0])
    # circuit.h(address_qregs[1])
    sparse_num = 2**np.random.randint(0,level+1)
    generate_sparse_state(precircuit,address_qregs,sparse_num= sparse_num)
    config0 = Config()
    config1 = Config()
    config1.decompose_mode = "subspace_decompose"
    config2 = Config()
    config2.decompose_mode = "subspace_decompose"
    results =[]
    print('sparse_num:',sparse_num)
    has_addnew = False
    for config in [config0,config1,config2]:
        qram = Qram(data, bandwidth=1,config=config)
        circuit = precircuit.copy()
        qram(circuit, address_qregs, bus_qregs)
        circuit = convert_to_layered_circuit(circuit)
        print(circuit.depth())
        addressbus = [circuit.find_bit(q) for q in address_qregs._bits] + [circuit.find_bit(q) for q in bus_qregs._bits]
        circuit.save_density_matrix(qubits=[q[0] for q in addressbus], label="rho", conditional=False) # conditional is set to True for considering the measurements
        # circuit.measure(bus_qregs,bus_cregs)
        noiseDensityMatrix = get_densitymatrix(circuit,noise = True)
        DensityMatrix = get_densitymatrix(circuit, noise = False)
        
        fidelity = state_fidelity(noiseDensityMatrix,DensityMatrix,validate=False)
        print("fidelity:",fidelity)
        results.append({
            "address_sparse": sparse_num,
            'data': data,
            'noisedensity': noiseDensityMatrix,
            'grd_density': DensityMatrix,
            'fidelity': fidelity,
            'config': config
        })
    print("_"*20)
    with open(f"results/level{level}/noisesim_qram_{i}.pkl", "wb") as f:
        pickle.dump(results, f)
    return results
if __name__ == "__main__":
    level = 3
    test_fidelity(0)
    exit()
    if not os.path.exists(f"results/level{level}/"):
        os.mkdir(f"results/level{level}/")
    res = ray.get([test_fidelity.remote(i) for i in range(1000)])
    with open(f"results/level{level}/noisesim_qram.pkl", "wb") as f:
        pickle.dump(res, f)
    
    