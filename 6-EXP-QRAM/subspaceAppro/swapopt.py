from qiskit import QuantumCircuit,transpile
from numpy import pi
from qiskit_aer import Aer
cir = QuantumCircuit(2)

cir.rz(5*pi/6,0)
cir.rz(5*pi/6,1)
cir.rx(pi/2,0)
cir.rx(pi/2,1)
cir.cz(0,1)
cir.rz(pi/2,0)
cir.rz(-pi,1)
cir.rx(pi/2,0)
cir.rx(pi/4,1)
cir.cz(0,1)
cir.rz(3*pi/4,0)
cir.rz(pi/2,1)
cir.rx(pi/2,0)
cir.rx(pi/2,1)

print(cir)
opt_circ = transpile(cir, basis_gates=['rz','cz','rx','ry','t'], coupling_map=[[0,1]], optimization_level=1)
print(opt_circ)
print(opt_circ.count_ops())
print(opt_circ.depth())
simulator = Aer.get_backend('unitary_simulator')
result = simulator.run(cir).result()
unitary = result.get_unitary()
print(unitary)

## cpflow opt
import numpy as np
from cpflow import *

# u_target = np.array([[1, 0, 0, 0, 0, 0, 0, 0],
#                      [0, 1, 0, 0, 0, 0, 0, 0],
#                      [0, 0, 1, 0, 0, 0, 0, 0],
#                      [0, 0, 0, 1, 0, 0, 0, 0],
#                      [0, 0, 0, 0, 1, 0, 0, 0],
#                      [0, 0, 0, 0, 0, 0, 1, 0],
#                      [0, 0, 0, 0, 0, 1, 0, 0],
#                      [0, 0, 0, 0, 0, 0, 0, -1]])
u_target = unitary
# u_target = np.array([[1, 0, 0, 0],
#                      [0, 1, 0, 0],
#                      [0, 0, 1, 0],
#                      [0, 0, 0, 1]])
layer = [[0, 1], [1, 2]]  # Linear connectivity
decomposer = Synthesize(layer, target_unitary=u_target, label='cswap')
options = StaticOptions(num_cp_gates=8, accepted_num_cz_gates=5, num_samples=20, target_loss=1e-8)
results = decomposer.static(options) # Should take from one to five minutes.

d = results.decompositions[0]  # This turned out to be the best decomposition for refinement.
d.refine()
print(d)
print(d.circuit.draw())
circuit : QuantumCircuit = d.circuit
circuit.qasm(formatted=True,filename='cswap.qasm')
print(counts)
def cnot(a,b):
    cir.h(b)
    cir.cz(a,b)
    cir.h(b)
    
def swap(a,b):
    cir.iswap(a,b)
    cir.s(a).inverse()
    cir.s(b).inverse()

def cswap(a,b,c,d): #第三位为|0>
    cir.cz(b,c)
    cir.rx(-pi/4,c)
    swap(d,a)
    cir.cz(d,c)
    cir.rx(pi/4,c)
    cir.cz(b,c)
    cir.rx(-pi/4,c)
    cir.rz(pi/4,b)
    cir.h(b)
    cir.cz(d,c)
    swap(a,d)
    cir.cz(a,b)
    cir.rx(pi/4,c)
    cir.rz(pi/4,a)
    cir.rx(-pi/4,b)
    cir.cz(a,b)
    cir.cz(c,b)
    cir.h(b)

# cswap(0,1,2,3)
# circ_opt, results = qmap.optimize_clifford(cir)
# print(circ_opt)
# print(results)