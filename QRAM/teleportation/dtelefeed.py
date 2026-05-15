from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister

cir = QuantumCircuit(6)
cregs = ClassicalRegister(2, 'c')
# cregs[1] = ClassicalRegister(1, 'c2')
# cir.add_register(cregs[0])
# cir.add_register(cregs[1])
cir.add_register(cregs)

def double_control_by_feedback(q,t1,t2):
    cir.cx(q[0],q[2])
    cir.ccx(q[0],q[1],q[3])
    cir.cx(q[3],q[2])
    cir.barrier(q)
    cir.cx(q[2],t1)
    cir.cx(q[3],t2)
    cir.barrier(q[2],q[3],t1,t2)
    cir.h(q[2])
    cir.h(q[3])
    cir.measure(2,cregs[0])
    cir.measure(3,cregs[1])
    cir.barrier(q[2],q[3])
    cir.cz(q[1],q[0]).c_if(cregs, 0x01)
    cir.x(q[1]).c_if(cregs, 0x10)
    cir.cz(q[1],q[0]).c_if(cregs,0x10)
    cir.x(q[1]).c_if(cregs,0x10)
    cir.z(q[0]).c_if(cregs,0x11)
    cir.barrier(q[0],q[1])

def double_control_by_cwap(q,t1,t2):
    cir.cswap(q[1],q[0],q[2])
    cir.x(q[1])
    cir.cswap(q[1],q[0],q[3])
    cir.x(q[1])
    cir.barrier(q)
    cir.cx(q[2],t1)
    cir.cx(q[3],t2)
    cir.barrier(q[2],q[3],t1,t2)
    cir.cswap(q[1],q[0],q[2])
    cir.x(q[1])
    cir.cswap(q[1],q[0],q[3])
    cir.x(q[1])
    # cir.x(q[1]).c_if(2,'1')
    # cir.cz(q[1],q[0]).c_if(23, 1)
    # cir.x(q[1]).c_if(2,'1')
    # cir.z(q[0]).c_if(23,'11')
double_control_by_feedback([0,1,2,3],4,5)
from qiskit import transpile
transpiled_cir = transpile(cir, basis_gates=['rz','cz','h'],coupling_map=[[0,1],[1,2],[1,3],[2,4],[3,5]])
print(transpiled_cir.count_ops())



