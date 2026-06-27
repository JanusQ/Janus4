from qiskit import QuantumCircuit, transpile, QuantumRegister, ClassicalRegister
from qiskit_aer import Aer
from qiskit.circuit.library import RYGate, RZGate
import numpy as np
Decompose_CSWAP = False
def cswap(cir:QuantumCircuit,*q):
    if Decompose_CSWAP:
        cir.rz(1.9986164569854736,q[1])
        cir.rx(0.1859593391418457,q[1])
        cir.cz( q[0],q[1])
        cir.rx(3.1414453983306885,q[0])
        cir.rz(0.39461636543273926,q[1])
        cir.rx(1.570793867111206,q[1])
        cir.rz(-2.325270414352417,q[2])
        cir.rx(1.4996445178985596,q[2])
        cir.cz( q[1],q[2])
        cir.rz(-3.141577959060669,q[1])
        cir.rx(2.356193780899048,q[1])
        cir.cz( q[0],q[1])
        cir.rx(3.141592264175415,q[0])
        cir.rz(-3.1415770053863525,q[1])
        cir.rx(0.8390493392944336,q[1])
        cir.rz(1.6863858699798584,q[2])
        cir.rx(1.6270678043365479,q[2])
        cir.cz( q[1],q[2])
        cir.rz(-1.5705323219299316,q[1])
        cir.rx(1.5710699558258057,q[1])
        cir.rz(-2.3577821254730225,q[2])
        cir.rx(1.5707881450653076,q[2])
        cir.cz( q[1],q[2])
        cir.rz(2.3577845096588135,q[1])
        cir.rx(1.6270687580108643,q[1])
        cir.cz( q[0],q[1])
        cir.rz(0.785407304763794,q[0])
        cir.rz(-1.5144445896148682,q[1])
        cir.rx(0.7853965759277344,q[1])
        cir.rx(1.5707967281341553,q[2])
        cir.cz( q[1],q[2])
        cir.rx(0.7854020595550537,q[1])
        cir.rz(-1.6244618892669678,q[2])
        cir.rx(1.5710680484771729,q[2])
        cir.cz( q[1],q[2])
        cir.rz(-0.1719667911529541,q[1])
        cir.rx(1.4999163150787354,q[1])
        cir.rz(-0.8163588047027588,q[1])
        cir.rz(-1.4985880851745605,q[2])
        cir.rx(1.399273157119751,q[2])
        cir.rz(-2.39945387840271,q[2])
    else:
        cir.cswap(*q)

class RouterQubit:
    def __init__(self, index, level, direction, root):
        self.index = index
        self.level = level
        self.root = root
        self.left_router = None
        self.right_router = None
        self.direction = direction
        
        self.qreg = QuantumRegister(1,self.reg_name)

    @property
    def address(self):
        if self.root is None:
            return self.direction
        else:
            return self.root.address + self.direction

    @property
    def reg_name(self):
        if self.address:
            return f"router_{self.level}_{self.address}"
        else:
            return f"router_{self.level}"

    def add_leaf_qubits(self, circuit):
        self.left =  QuantumRegister(1,self.reg_name + '_l')
        self.right =  QuantumRegister(1,self.reg_name + '_r')
        circuit.add_register(self.left)
        circuit.add_register(self.right)
    
    def add_data_qubits(self, circuit):
        self.data =  QuantumRegister(1,self.reg_name + '_data')
        circuit.add_register(self.data)
        
class Qram:
    def __init__(self, address, data,*regs, bandwidth=1):
        self.address = address
        self.data = data
        self.bandwidth = bandwidth
        self.apply_classical_bit = True
        self.circuit = QuantumCircuit(*regs)
        self.routers = [[] for _ in range(len(address))]
    def add_router_tree(self, level,root):
        self.circuit.add_register(root.qreg)
        if root.left_router is not None:
            self.circuit.add_register(root.left_router.qreg)
        if root.right_router is not None:
            self.circuit.add_register(root.right_router.qreg)
        self.routers[level].append(root)
        if root.left is not None:
            self.add_router_tree(level + 1, root.left)
        if root.right is not None:
            self.add_router_tree(level + 1, root.right)

    def add_incident_qubits(self, incident):
        self.incident = incident
        self.circuit.add_register(self.incident.qreg)

    def __call__(self,address_qubits, bus_qubits):
        
        self.address_qubits = address_qubits
        self.bus_qubits = bus_qubits
        self.decompose_circuit(self.circuit)

    def router(self, circuit: QuantumCircuit, router: QuantumRegister, incident, left, right):
        circuit.x(router)
        cswap(circuit,router, incident, left)
        circuit.x(router)
        cswap(circuit,router, incident, right)

    def reverse_router(self, circuit: QuantumCircuit, router, incident, left, right):
        cswap(circuit,router, incident, right)
        circuit.x(router)
        cswap(circuit,router, incident, left)
        circuit.x(router)

    def layers_router(self, circuit, router_obj, incident, address_index, mid):
        if router_obj.level == 0:
            circuit.swap(incident, mid.qreg)
        if router_obj.level == 0 and address_index == 0:
            circuit.swap(router_obj.qreg, mid.qreg)
        else:
            if router_obj.level + 2 == address_index and address_index == len(self.address_qubits):
                self.router(circuit, router_obj.qreg, mid.qreg, router_obj.left.qreg, router_obj.right.qreg)
                return
            
            self.router(circuit, router_obj.qreg, mid.qreg, router_obj.left_router.qreg, router_obj.right_router.qreg)
            if router_obj.level + 1 == address_index:
                if router_obj.left_router.qreg != router_obj.left:
                    circuit.swap(router_obj.left_router.qreg, router_obj.left.qreg)
                if router_obj.right_router.qreg != router_obj.right:
                    circuit.swap(router_obj.right_router.qreg, router_obj.right.qreg)
                return
            if router_obj.left is not None:
                self.layers_router(circuit, router_obj.left, router_obj.left_router, address_index, router_obj.left_router)
            if router_obj.right is not None:
                self.layers_router(circuit, router_obj.right,router_obj.right_router,  address_index, router_obj.right_router)

    def reverse_layers_router(self, circuit, router_obj, incident, address_index, mid):
        if address_index != 0:
            if router_obj.level + 1 > address_index:
                return
            if router_obj.right is not None:
                self.reverse_layers_router(circuit, router_obj.right,router_obj.right_router,  address_index, router_obj.right_router)
            if router_obj.left is not None:
                self.reverse_layers_router(circuit, router_obj.left, router_obj.left_router, address_index, router_obj.left_router)
            if router_obj.level + 2 == address_index and address_index == len(self.address_qubits):
                self.router(circuit, router_obj.qreg, mid.qreg, router_obj.left.qreg, router_obj.right.qreg)
                return
            elif router_obj.level + 1 == address_index and address_index != len(self.address_qubits):
                if router_obj.left_router.qreg != router_obj.left:
                    circuit.swap(router_obj.left_router.qreg, router_obj.left.qreg)
                if router_obj.right_router.qreg != router_obj.right:
                    circuit.swap(router_obj.right_router.qreg, router_obj.right.qreg)
            if router_obj.right_router is not None:
                self.reverse_router(circuit, router_obj.qreg, mid.qreg, router_obj.left_router.qreg, router_obj.right_router.qreg)
            
            
            
        else:
            circuit.swap(router_obj.qreg,  mid.qreg)
        if router_obj.level == 0:
            circuit.swap(incident,  mid.qreg )

    def decompose_circuit(self, circuit):
        for idx in self.bus_qubits:
            circuit.h(idx)
        incidents = {i:self.address_qubits[i] for i in range(self.address_qubits._size)}
        incidents.update({i+self.address_qubits._size:self.bus_qubits[i] for i in range(self.bus_qubits._size)})
        for idx in range(len(incidents)):
            self.layers_router(circuit, self.routers[0][0], incidents[idx], idx, self.incident)
            circuit.barrier()
        for router_obj in self.routers[-1]:
            if self.data[int(router_obj.address + '1', 2)] == 1:
                circuit.cz(router_obj.qreg, router_obj.data)
            # else:
            #     circuit.cz(router_obj.qreg, router_obj.data)

            if self.data[int(router_obj.address + '0', 2)] == 1:
                circuit.x(router_obj.qreg)
                circuit.cz(router_obj.qreg, router_obj.data)
                circuit.x(router_obj.qreg)
        circuit.barrier()
        for idx in reversed(range(len(self.address_qubits) + 1)):
            self.reverse_layers_router(circuit, self.routers[0][0], incidents[idx], idx, self.incident)
            circuit.barrier()
            
        for idx in self.bus_qubits:
            circuit.h(idx)
def generate_grid_coupling_map(width, height):
    coupling_map = []
    for i in range(width):
        for j in range(height):
            if i < width - 1:
                coupling_map.append([i*height+j, (i+1)*height+j])
            if j < height - 1:
                coupling_map.append([i*height+j, i*height+j+1])
    return coupling_map

def plot_coupling_map(coupling_map, width, height):
    import matplotlib.pyplot as plt
    plt.figure(figsize=(width, height))
    for i in range(width):
        for j in range(height):
            plt.text(i, j, str(i*height+j), ha='center', va='center', fontsize=12)
            for edge in coupling_map:
                plt.plot([edge[0]%height, edge[1]%height], [edge[0]//height, edge[1]//height], 'k-')
    plt.axis('off')
    plt.show()

def cz_depth(circuit):
    new_circuit = QuantumCircuit(*circuit.qregs, *circuit.cregs)
    for gate in circuit.data:
        if gate[0].name == 'cz':
            new_circuit.data.append(gate)
    
    return new_circuit.depth()
            
if __name__ == "__main__":
    address = [bin(i)[2:].zfill(3) for i in range(8)]
    # data = [i / 8 for i in range(8)]
    data = [0,0,1,1,1,0,0,1]
    address_qregs = QuantumRegister(3, 'address')
    bus_qregs = QuantumRegister(1, 'bus')
    bus_cregs = ClassicalRegister(1, 'bus_classical')
    address_cregs = ClassicalRegister(3, 'address_classical')
    circuit = QuantumCircuit(address_qregs, bus_qregs, address_cregs,bus_cregs)
    circuit.h(address_qregs[0])
    circuit.h(address_qregs[1])
    circuit.h(address_qregs[2])
    qram = Qram(address, data, bandwidth=1)
    qram(circuit, address_qregs, bus_qregs)
    circuit.measure(bus_qregs,bus_cregs)
    circuit.measure(address_qregs,address_cregs)
    print(circuit.num_qubits)
    simulator = Aer.get_backend('qasm_simulator')
    result = simulator.run(circuit,shots=10000).result()
    counts = result.get_counts(circuit)
    print("测量结果：",{k[::-1]:v/10000 for k,v in counts.items()})
    transpiled_circuit = transpile(circuit,basis_gates=['rx','rz','cz'],optimization_level=3)
    print("cz 深度:",cz_depth(transpiled_circuit))
    
    print("门数量:",transpiled_circuit.count_ops())
    coupling_map = generate_grid_coupling_map(4,5)
    # plot_coupling_map(coupling_map, 5, 5)
    print(coupling_map)
    
    # transpiled_circuit = transpile(circuit,coupling_map=coupling_map,basis_gates=['x','h','cswap','swap','rz','cz'])
    transpiled_circuit = transpile(circuit,coupling_map=coupling_map,basis_gates=['rx','rz','cz'])
    # print(transpiled_circuit)
    result = simulator.run(transpiled_circuit).result()
    counts = result.get_counts(circuit)
    print(counts)
    print("cz 深度:",cz_depth(transpiled_circuit))
    
    print("门数量:",transpiled_circuit.count_ops())
    print(transpiled_circuit.layout.input_qubit_mapping)
