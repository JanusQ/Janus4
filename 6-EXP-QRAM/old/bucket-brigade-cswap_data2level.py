from qiskit import QuantumCircuit, transpile, QuantumRegister, ClassicalRegister
from qiskit_aer import Aer
from math import pi
Decompose_CSWAP = True
DSWAP_Embedding = True
def control_cswap(cir, data, control, target1, target0):
    qasm_file_path = 'gates/cswap_control_mid.qasm'
    circuit_from_qasm = QuantumCircuit.from_qasm_file(qasm_file_path)
    q = [control,data, target1, target0]
    ## topology: control -> data , control -> target1, control -> target0
    # 将 circuit_from_qasm 添加到新电路的指定比特上
    cir.compose(circuit_from_qasm, qubits=q, inplace=True)


def cswap(cir:QuantumCircuit,*q):
    if Decompose_CSWAP:
        cir.rx(pi,q[0])
        cir.rz(3.0797979831695557,q[1])
        cir.rx(1.5425798892974854,q[1])
        cir.rz(3.079930067062378,q[2])
        cir.rx(pi/2,q[2])
        cir.cz(q[1],q[2])
        cir.rx(pi/4,q[1])
        cir.rz(-pi,q[2])
        cir.rx(pi/4,q[2])
        cir.cz(q[1],q[2])
        cir.rx(1.5907633304595947,q[1])
        cir.cz(q[0],q[1])
        cir.rx(pi,q[0])
        cir.rz(-pi,q[0])
        cir.rz(2.5871939500151235,q[1])
        cir.rx(1.550781488418579,q[1])
        cir.rz(pi/2,q[2])
        cir.rx(2.5871939500151235,q[2])
        cir.cz(q[1],q[2])
        cir.rx(pi/4,q[1])
        cir.rz(pi/2,q[2])
        cir.rx(pi/4,q[2])
        cir.cz(q[1],q[2])
        cir.rx(1.599186658859253,q[1])
        cir.rz(2.650718801466388,q[1])
        cir.rz(pi,q[2])
        cir.rx(pi/2,q[2])
        cir.rz(2.650718801466388,q[2])
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
    def __init__(self, address, data, bandwidth=1):
        self.address = address
        self.data = data
        self.bandwidth = bandwidth
        self.apply_classical_bit = True

    def generate_router_tree(self, level, direction, root, circuit:QuantumCircuit):
        router = RouterQubit(self.cur_index, level, direction, root)
        circuit.add_register(router.qreg)
        if level < len(self.address_qubits)-2:
            router.add_leaf_qubits(circuit)
        
        self.cur_index += 1
        if level == len(self.address_qubits) - 1:
            router.add_data_qubits(circuit)
            self.routers[level].append(router)
            
            return router
        router.left_router = self.generate_router_tree(level + 1, '0', router, circuit)
        router.right_router = self.generate_router_tree(level + 1, '1', router, circuit)
        if level == len(self.address_qubits)-2:
            router.left = router.left_router.qreg
            router.right = router.right_router.qreg
        self.routers[level].append(router)
        return router

    def assign_qubits(self,circuit):
        self.cur_index = 0
        self.routers = [[] for _ in self.address_qubits]
        self.generate_router_tree(0, '', None,circuit)

    def __call__(self,circuit, address_qubits, bus_qubits):
        
        self.address_qubits = address_qubits
        self.bus_qubits = bus_qubits
        # input_qubit = QuantumRegister(1, 'incident')
        # circuit.add_register(input_qubit)
        self.incident = None
        self.assign_qubits(circuit)
        self.decompose_circuit(circuit)

        return circuit
    def router(self, circuit: QuantumCircuit, router: QuantumRegister, incident, left, right):
        if DSWAP_Embedding:
            control_cswap(circuit,incident,router._bits[0], right, left)
        else:
            circuit.x(router)
            cswap(circuit,router, incident, left)
            circuit.x(router)
            cswap(circuit,router, incident, right)

    def reverse_router(self, circuit, router, incident, left, right):
        cswap(circuit,router, incident, right)
        circuit.x(router)
        cswap(circuit,router, incident, left)
        circuit.x(router)

    def layers_router(self, circuit, router_obj, incident, address_index, mid):
        if router_obj.level == 0:
            mid = incident
        if router_obj.level == 0 and address_index == 0:
            circuit.swap(router_obj.qreg, mid)
        else:
            if router_obj.level + 2 == address_index and address_index == len(self.address_qubits):
                self.router(circuit, router_obj.qreg, mid, router_obj.left_router.data, router_obj.right_router.data)
                return
            if not hasattr(router_obj, 'data'):
                self.router(circuit, router_obj.qreg, mid, router_obj.left, router_obj.right)
            if router_obj.left_router is not None:
                self.layers_router(circuit, router_obj.left_router, router_obj.left, address_index, router_obj.left)
            if router_obj.right_router is not None:
                self.layers_router(circuit, router_obj.right_router, router_obj.right, address_index, router_obj.right)
        circuit.barrier()
    def reverse_layers_router(self, circuit, router_obj, incident, address_index, mid):
        if router_obj.level == 0:
            mid = incident
        if address_index != 0:
            if router_obj.level + 1 > address_index:
                return
            if router_obj.right_router is not None:
                self.reverse_layers_router(circuit, router_obj.right_router, router_obj.right, address_index, router_obj.right)
            if router_obj.left_router is not None:
                self.reverse_layers_router(circuit, router_obj.left_router, router_obj.left, address_index, router_obj.left)
            # if router_obj.level + 2 == address_index:
            #     if router_obj.right_router is not None:
            #         circuit.swap(router_obj.right_router.qreg, router_obj.right)
            #     if router_obj.left_router is not None:
            #         circuit.swap(router_obj.left_router.qreg, router_obj.left)
            
            if router_obj.level + 2 == address_index and address_index == len(self.address_qubits):
                self.router(circuit, router_obj.qreg, mid, router_obj.left_router.data, router_obj.right_router.data)
            elif not hasattr(router_obj, 'data'):
                self.reverse_router(circuit, router_obj.qreg, mid, router_obj.left, router_obj.right)
        else:
            circuit.swap(router_obj.qreg, mid)
        
        circuit.barrier()
        
    def decompose_circuit(self, circuit):
        
        for idx in self.bus_qubits:
            circuit.h(idx)
        incidents = {i:self.address_qubits[i] for i in range(self.address_qubits._size)}
        incidents.update({i+self.address_qubits._size:self.bus_qubits[i] for i in range(self.bus_qubits._size)})
        for idx in range(len(incidents)):
            self.layers_router(circuit, self.routers[0][0], incidents[idx], idx, self.incident)
        for router_obj in self.routers[-1]:
            if self.data[int(router_obj.address + '1', 2)] == 1:
                circuit.cz(router_obj.qreg, router_obj.data)
            # else:
            #     circuit.cz(router_obj.qreg, router_obj.data)

            if self.data[int(router_obj.address + '0', 2)] == 1:
                circuit.x(router_obj.qreg)
                circuit.cz(router_obj.qreg, router_obj.data)
                circuit.x(router_obj.qreg)
            # else:
            #     circuit.x(router_obj.qreg)
            #     circuit.cz(router_obj.qreg, router_obj.data)
            #     circuit.x(router_obj.qreg)
        for idx in reversed(range(len(self.address_qubits) + 1)):
            self.reverse_layers_router(circuit, self.routers[0][0], incidents[idx], idx, self.incident)
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

if __name__ == "__main__":
    address = [bin(i)[2:].zfill(3) for i in range(2)]
    # data = [i / 8 for i in range(8)]
    data = [1,0,1,1]
    address_qregs = QuantumRegister(2, 'address')
    bus_qregs = QuantumRegister(1, 'bus')
    bus_cregs = ClassicalRegister(1, 'bus_classical')
    address_cregs = ClassicalRegister(2, 'address_classical')
    circuit = QuantumCircuit(address_qregs, bus_qregs, address_cregs,bus_cregs,name='QRAM')
    circuit.h(address_qregs[0])
    circuit.h(address_qregs[1])
    Decompose_CSWAP = True
    qram = Qram(address, data, bandwidth=1)
    qram(circuit, address_qregs, bus_qregs)
    circuit.measure(bus_qregs,bus_cregs)
    circuit.measure(address_qregs,address_cregs)
    print(circuit.count_ops())
    print(circuit.num_qubits)
    print(circuit)
    # exit()
    simulator = Aer.get_backend('qasm_simulator')
    result = simulator.run(circuit).result()
    counts = result.get_counts(circuit)
    print(counts)
    coupling_map = generate_grid_coupling_map(3,6)
    # plot_coupling_map(coupling_map, 5, 5)
    print(coupling_map)
    
    # transpiled_circuit = transpile(circuit,coupling_map=coupling_map,basis_gates=['x','h','cswap','swap','rz','cz'])
    transpiled_circuit = transpile(circuit,coupling_map=coupling_map,basis_gates=['rx','rz','cz'],initial_layout='')
    print(transpiled_circuit)
    print(transpiled_circuit.count_ops())
    result = simulator.run(transpiled_circuit,shots=1000).result()
    counts = result.get_counts(circuit)
    print("测量结果：",{k[::-1]:v/1000 for k,v in counts.items()})
