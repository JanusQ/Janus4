from qiskit import QuantumCircuit,transpile,ClassicalRegister
from numpy import pi
from qiskit_aer import Aer


cir = QuantumCircuit(4,2)
# 0 - 1 ->2 OR -> 3
# cir.h(0)
# cir.x(1)
cir.cx(0,2)
cir.ccx(0,1,3)
cir.cx(3,2)
cir.h(0)
cir.measure(0,0)
cir.z(2).c_if(0,1)
cir.z(3).c_if(0,1)
c_res = ClassicalRegister(1,name='m')
cir.add_register(c_res)
cir.measure(3,c_res)
print(cir)
layer = [[0,1],[1,2],[1,3]]
opt_circ = transpile(cir, basis_gates=['rz','cz','h'], 
                     coupling_map=layer, 
                     optimization_level=2)
# opt_circ = transpile(cir, basis_gates=['rz','cz','h'],  optimization_level=1)
print(opt_circ)
print(opt_circ.count_ops())
print(opt_circ.depth())

simulator = Aer.get_backend('qasm_simulator')
result = simulator.run(transpile(opt_circ, simulator)).result()
counts = result.get_counts(opt_circ)
print(counts) 

## GET the unitary of circuit
templete= QuantumCircuit(4)
templete.cx(0,2)
templete.ccx(0,1,3)
templete.cx(3,2)
## get the unitary of circuit
simulator = Aer.get_backend('unitary_simulator')
unitary = simulator.run(templete).result().get_unitary()
print(unitary)

from cpflow import *
decomposer = Synthesize(layer, target_unitary=unitary, label='cswaptele')
options = StaticOptions(num_cp_gates=15, accepted_num_cz_gates=12, num_samples=10,target_loss=1e-10)
results = decomposer.static(options) # Should take from one to five minutes.
d = results.decompositions[0]  # This turned out to be the best decomposition for refinement.
d.refine()
print(d)
circuit : QuantumCircuit = d.circuit
circuit.qasm(formatted=True,filename='doubletele.qasm')
