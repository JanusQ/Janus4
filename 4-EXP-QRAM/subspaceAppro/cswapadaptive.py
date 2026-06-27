## cpflow opt
import numpy as np
from cpflow import *
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
import jax.numpy as jnp

u_target = np.array([[1, 0, 0, 0, 0, 0, 0, 0],
                     [0, 1, 0, 0, 0, 0, 0, 0],
                     [0, 0, 1, 0, 0, 0, 0, 0],
                     [0, 0, 0, 1, 0, 0, 0, 0],
                     [0, 0, 0, 0, 1, 0, 0, 0],
                     [0, 0, 0, 0, 0, 0, 1, 0],
                     [0, 0, 0, 0, 0, 1, 0, 0],
                     [0, 0, 0, 0, 0, 0, 0, -1]])

def unitary_loss_func(u):
    n = u.shape[0]
    # mapbits = [(0,0),(2,2),(4,4),(5,6),(6,5)]
    mapbits = [(0,0),(4,4),(12,5),(8,2),(5,12),(2,8)]
    # 0000 0100 1100->0101 1000->0010
    
    cost = 0
    for bits in mapbits:
        target = np.zeros(n)
        target[bits[0]] = 1
        diff = u[:,bits[1]]- target
        # print(diff)
        cost += jnp.abs(jnp.vdot(diff,diff.conj())) ** 2 / n                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
        target = np.zeros(n)
        target[bits[1]] = 1
        diff = u[bits[0],:]- target
        cost += jnp.abs(jnp.vdot(diff,diff.conj())) ** 2 / n
        # print(cost)
    # for i in range(n):
    #     for j in range(i+1,n):
    #         if i not in [bits[0] for bits in mapbits] and j not in [bits[1] for bits in mapbits]:
            
    return cost

# print(unitary_loss_func(u_target))
# exit()

layer = [[0, 1], [1, 2]]  # Linear connectivity
decomposer = Synthesize(layer, target_unitary=u_target, label='d_cswap')
options = AdaptiveOptions(min_num_cp_gates=10,max_num_cp_gates=36,target_num_cz_gates=8,keep_logs=True,threshold_cp=0.05,rotation_gates='xz',max_evals=100,entry_loss=1e-4)
results = decomposer.adaptive(options, save_results=True)
# print(results.best_hyperparameters())
for d in results.decompositions:
    d.refine()
    print(d.loss)
    if d.loss < 1e-6:
        print(d.circuit.draw())
        circuit : QuantumCircuit = d.circuit
        circuit.qasm(formatted=True,filename=f'results/dcsw/dcswap_{d.loss}.qasm')