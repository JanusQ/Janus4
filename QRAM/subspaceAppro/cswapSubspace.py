## cpflow opt
import numpy as np
from cpflow import *
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
import jax.numpy as jnp

# u_target = np.array([[1, 0, 0, 0, 0, 0, 0, 0],
#                      [0, 1, 0, 0, 0, 0, 0, 0],
#                      [0, 0, 1, 0, 0, 0, 0, 0],
#                      [0, 0, 0, 1, 0, 0, 0, 0],
#                      [0, 0, 0, 0, 1, 0, 0, 0],
#                      [0, 0, 0, 0, 0, 0, 1, 0],
#                      [0, 0, 0, 0, 0, 1, 0, 0],
#                      [0, 0, 0, 0, 0, 0, 0, -1]])

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
                
    return cost/len(mapbits)

# print(unitary_loss_func(u_target))
# exit()

layer = [[0, 1], [1, 2],[1,3]]  # Linear connectivity
decomposer = Synthesize(layer, unitary_loss_func=unitary_loss_func, label='Dcswap')
# options = AdaptiveOptions(min_num_cp_gates=10,max accepted_num_cz_gates=12, num_samples=200,learning_rate=0.1)
options = StaticOptions(num_cp_gates=30, accepted_num_cz_gates=8, num_samples=200,learning_rate=0.1,num_gd_iterations=5000,threshold_cp=0.1,rotation_gates='xz',num_gd_iterations_at_verification=10000,entry_loss=1e-4)
results = decomposer.static(options) # Should take from one to five minutes.
# print(results.best_hyperparameters())
for d in results.decompositions:
    d.refine()
    print(d.loss)
    print(d.circuit.draw())
    circuit : QuantumCircuit = d.circuit
    circuit.qasm(formatted=True,filename='cswap.qasm')