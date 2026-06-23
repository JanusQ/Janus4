
from qiskit import QuantumCircuit, transpile, QuantumRegister, ClassicalRegister
import numpy as np
from qram.qramtemplate.buckdatacell import Qram as BBQram
from qram.qramtemplate.fanoutdatacell import Qram as FanoutQram
from qram.utils.noisemodel import build_noise_model
from qiskit.quantum_info import state_fidelity
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qram.utils.layer_circuit import convert_to_layered_circuit
import ray
import pickle
import os
from itertools import product
from qram.config import Config
def get_densitymatrix(circuit,noise= False,rho_names=None,**kwargs):
    if noise:
        noise_bit_flip = build_noise_model(**kwargs)
        backend = AerSimulator(method='tensor_network',device='GPU',
                                noise_model=noise_bit_flip)
        result = backend.run(circuit).result()
    else:
        backend = AerSimulator(method='tensor_network',device='GPU',)
        result = backend.run(circuit).result()
    
    return {name:result.data()[name] for name in rho_names}

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
    circuit.save_density_matrix(qubits=addressqregs, label="init", conditional=False) # conditional is set to True for considering the measurements

def prepare_address(circuit,address_qregs,cmd):
    if cmd == 'bell':
        circuit.h(address_qregs[0])
        circuit.cx(address_qregs[0],address_qregs[1])
    else:
        for idx,bit in enumerate(cmd):
            if bit == '1':
                circuit.x(address_qregs[idx])
            elif bit == '+':
                circuit.h(address_qregs[idx])
            elif bit == '-':
                circuit.x(address_qregs[idx])
                circuit.h(address_qregs[idx])
        
    circuit.save_density_matrix(qubits=address_qregs, label="init", conditional=False) 



@ray.remote(num_gpus=1/40)
def test_fidelity(i,cmd,data,singleq_error_rate,twoq_error_rate):
    # data = [0]*(2**level)
    address_qregs = QuantumRegister(level, 'address')
    bus_qregs = QuantumRegister(1, 'bus')
    bus_cregs = ClassicalRegister(1, 'bus_classical')
    address_cregs = ClassicalRegister(level, 'address_classical')
    precircuit = QuantumCircuit(address_qregs, bus_qregs, address_cregs,bus_cregs)
    prepare_address(precircuit,address_qregs,cmd)
    config = Config()
    config.decompose_mode = "subspace_decompose"
    densities =[]

    for Qram in [BBQram,FanoutQram]:
        circuit = precircuit.copy()
        qram = Qram(data, bandwidth=1,config=config)
        qram(circuit, address_qregs, bus_qregs)
        circuit = convert_to_layered_circuit(circuit)
        addressbus = [circuit.find_bit(q) for q in address_qregs._bits] + [circuit.find_bit(q) for q in bus_qregs._bits]
        router_names= []
        for idx,q in enumerate(circuit.qubits):
            qname = q._register._name
            if 'router' in qname and 'data' not in qname:
                circuit.save_density_matrix(qubits=[q], label=qname, conditional=False) 
                router_names.append(qname)
        circuit.save_density_matrix(qubits=[q[0] for q in addressbus], label="rho", conditional=False) # 
        rho_names = ['init','rho']+router_names
        noiseDensityMatrixs = get_densitymatrix(circuit,noise = True, rho_names=rho_names,
                                                p_gate_cz = twoq_error_rate,
                                                p_gate_single = singleq_error_rate,
                                                p_gate_id = singleq_error_rate,
                                                )
        DensityMatrixs = get_densitymatrix(circuit, noise = False,rho_names=rho_names)
        fidelities = {
            'address': cmd,
            'data': data,
            'qram': qram.name,
            '1qerror_rate':singleq_error_rate,
            '2qerror_rate':twoq_error_rate,
        }
        for name in rho_names:
            fidelities['fidelity_'+name] = state_fidelity(noiseDensityMatrixs[name],DensityMatrixs[name],validate=False)
        
        print(f"address: {cmd}, data: {data}, qram: {qram.name}, 1qerror_rate: {singleq_error_rate}, 2qerror_rate: {twoq_error_rate}, fidelity: {fidelities['fidelity_rho']}")
        densities.append({
            'noise': noiseDensityMatrixs,
            'ideal': DensityMatrixs,
            'address': cmd,
            'data': data,
            'qram': qram.name,
            '1qerror_rate':singleq_error_rate,
            '2qerror_rate':twoq_error_rate,
            
        })
        print("_"*20)
        with open(f"{savedir}densities_qram_{i}.pkl", "wb") as f:
            pickle.dump(densities, f)
        yield fidelities

def generate_address_data(level):
    for cmd in product(['0','1','+'], repeat=level):
        for data in product(['0','1'], repeat=2**level):
            yield ''.join(cmd),[int(x) for x in list(data)]
    # prepare GHZ state
    if level == 2:
        for partial_data in product(['0','1'], repeat=level):
            data = ['0'] + list(partial_data) + ['0']
            yield 'bell',[int(x) for x in data]


if __name__ == "__main__":
    level = 2
    savedir = f'results/level{level}_Errorrates/'
    if not os.path.exists(f"{savedir}"):
        os.mkdir(f"{savedir}")
    Singleqerror_rates = np.arange(1e-4,8e-4,1e-4)
    twoqerror_rates = np.arange(1e-3,11e-3,1e-3)
    # list(test_fidelity(0,*list(generate_address_data(level))[0],1e-4,1e-3))
    # exit()
    res = ray.get([list(test_fidelity.remote(i,cmd,data,singleq_error_rate,twoq_error_rate)) for i,(cmd,data) in enumerate(generate_address_data(level)) for singleq_error_rate in Singleqerror_rates for twoq_error_rate in twoqerror_rates])
    with open(f"{savedir}noisesim_qram.pkl", "wb") as f:
        pickle.dump(res, f)
    
    