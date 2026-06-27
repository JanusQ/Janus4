from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from math import pi
def control_cswap(cir, target, control, left, right):
    qasm_file_path = 'gates/cswap_control_mid.qasm'
    circuit_from_qasm = QuantumCircuit.from_qasm_file(qasm_file_path)
    q = [control,left,right,target]
    ## topology: control -> data , control -> target1, control -> target0
    # 将 circuit_from_qasm 添加到新电路的指定比特上
    cir.compose(circuit_from_qasm, qubits=[qi._bits[0] for qi in q], inplace=True)


def control_cswap_reverse(cir, target, control, left, right):
    qasm_file_path = 'gates/cswap_control_mid.qasm'
    circuit_from_qasm = QuantumCircuit.from_qasm_file(qasm_file_path)
    q = [control,left,right,target]
    ## topology: control -> data , control -> target1, control -> target0
    # 将 circuit_from_qasm 添加到新电路的指定比特上
    cir.compose(circuit_from_qasm.inverse(), qubits=[qi._bits[0] for qi in q], inplace=True)


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
    def __init__(self,address, data, bandwidth=1, config=None):
        self.address = address
        self.name = "Bucket-Brigade"
        self.data = data
        self.bandwidth = bandwidth
        self.decompose_mode = config.decompose_mode
        self.load_bus = config.load_bus
        self.dcswap_embedding = config.dcswap_embedding
        self.apply_classical_bit = True
        self.reg_routers = []

    def generate_router_tree(self, level, direction, root, circuit:QuantumCircuit):
        router = RouterQubit(self.cur_index, level, direction, root)
        circuit.add_register(router.qreg)
        self.reg_routers.append(router)
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

    def cswap(self,cir:QuantumCircuit,*q):
        if self.decompose_mode=='cswap_decompose':
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
        elif self.decompose_mode == "subspace_decompose":
            a,b,c = q
            cir.rx(pi,a)
            cir.rz(-1.9344532489776611,b)
            cir.rz(1.214379072189331,c)
            cir.rx(3.124248743057251,b)
            cir.rx(1.5707943439483643,c)
            cir.cz(b,c)
            cir.rz(3.1343448162078857,b)
            cir.rx(0.7853982448577881,b)
            cir.rz(-3.1415913105010986,c)
            cir.rx(1.5881779193878174,c)
            cir.cz(b,c)
            cir.rz(3.1415913105010986,b)
            cir.rx(2.3560431003570557,b)
            cir.cz(a,b)
            cir.rx(pi,a)
            cir.rx(2.3560431003570557,b)
            cir.cz(b,c)
            cir.rx(2.3561947345733643,b)
            cir.rx(1.553415060043335,c)
            cir.cz(b,c)
            cir.rx(0.01736760139465332,b)
            cir.rz(1.9268419742584229,b)
            cir.rx(1.5708487033843994,c)
            cir.rz(-1.2143813371658325,c)
        else:
            cir.cswap(*q)

        
    def assign_qubits(self,circuit):
        self.cur_index = 0
        self.routers = [[] for _ in self.address_qubits]
        self.generate_router_tree(0, '', None,circuit)

    def __call__(self,circuit, address_qubits, bus_qubits):
        
        self.address_qubits = address_qubits
        self.bus_qubits = bus_qubits
        input_qubit = QuantumRegister(1, 'incident')
        circuit.add_register(input_qubit)
        self.incident = input_qubit
        self.assign_qubits(circuit)
        self.decompose_circuit(circuit)

        return circuit
    def router(self, circuit: QuantumCircuit, router: QuantumRegister, incident, left, right):
        # if DSWAP_Embedding:
        #     control_cswap(circuit,incident,router, left, right)
        # else:
        circuit.x(router)
        self.cswap(circuit,router, incident, left)
        circuit.x(router)
        self.cswap(circuit,router, incident, right)

    def reverse_router(self, circuit: QuantumCircuit, router, incident, left, right):
        if self.dcswap_embedding:
            control_cswap_reverse(circuit,incident,router, left, right)
        else:
            self.cswap(circuit,router, incident, right)
            circuit.x(router)
            self.cswap(circuit,router, incident, left)
            circuit.x(router)

    def layers_router(self, circuit, router_obj, incident, address_index, mid):
        if router_obj.level == 0:
            circuit.swap(incident, mid)
        if router_obj.level == 0 and address_index == 0:
            circuit.swap(router_obj.qreg, mid)
        else:
            if router_obj.level + 2 == address_index and address_index == len(self.address_qubits):
                self.router(circuit, router_obj.qreg, mid, router_obj.left_router.data, router_obj.right_router.data)
                return
            
            # self.router(circuit, router_obj.qreg, mid, router_obj.left, router_obj.right)
            if not hasattr(router_obj, 'data'):
                self.router(circuit, router_obj.qreg, mid, router_obj.left, router_obj.right)
            if router_obj.level + 1 == address_index:
                if router_obj.left_router.qreg != router_obj.left:
                    circuit.swap(router_obj.left_router.qreg, router_obj.left)
                if router_obj.right_router.qreg != router_obj.right:
                    circuit.swap(router_obj.right_router.qreg, router_obj.right)
                return
            if router_obj.left_router is not None:
                self.layers_router(circuit, router_obj.left_router, router_obj.left, address_index, router_obj.left)
            if router_obj.right_router is not None:
                self.layers_router(circuit, router_obj.right_router, router_obj.right, address_index, router_obj.right)

    def reverse_layers_router(self, circuit, router_obj, incident, address_index, mid):
        if address_index != 0:
            if router_obj.level + 1 > address_index:
                return
            if router_obj.right_router is not None:
                self.reverse_layers_router(circuit, router_obj.right_router, router_obj.right, address_index, router_obj.right)
            if router_obj.left_router is not None:
                self.reverse_layers_router(circuit, router_obj.left_router, router_obj.left, address_index, router_obj.left)
            if router_obj.level + 2 == address_index and address_index == len(self.address_qubits):
                self.router(circuit, router_obj.qreg, mid, router_obj.left_router.data, router_obj.right_router.data)
            elif router_obj.level + 1 == address_index and address_index != len(self.address_qubits):
                if router_obj.left_router.qreg != router_obj.left:
                    circuit.swap(router_obj.left_router.qreg, router_obj.left)
                if router_obj.right_router.qreg != router_obj.right:
                    circuit.swap(router_obj.right_router.qreg, router_obj.right)
                if not hasattr(router_obj, 'data'):
                    self.reverse_router(circuit, router_obj.qreg, mid, router_obj.left, router_obj.right)
                    
            elif not hasattr(router_obj, 'data'):
                self.reverse_router(circuit, router_obj.qreg, mid, router_obj.left, router_obj.right)
            
            
            
        else:
            circuit.swap(router_obj.qreg, mid)
        if router_obj.level == 0:
            circuit.swap(incident, mid)

    def decompose_circuit(self, circuit):
        if self.load_bus:
            for idx in self.bus_qubits:
                circuit.h(idx)
        incidents = {i:self.address_qubits[i] for i in range(self.address_qubits._size)}
        incidents.update({i+self.address_qubits._size:self.bus_qubits[i] for i in range(self.bus_qubits._size)})
        if self.load_bus:
            incidents_len = len(incidents)
        else:
            incidents_len = len(incidents)-1
        for idx in range(incidents_len):
            self.layers_router(circuit, self.routers[0][0], incidents[idx], idx, self.incident)
            circuit.barrier()
        for router_obj in self.routers[-1]:
            if not self.load_bus:
                circuit.h(router_obj.data)
            if self.data[int(router_obj.address + '1', 2)] == 1:
                circuit.cz(router_obj.qreg, router_obj.data)
            
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

def cswap_depth(circuit):
    new_circuit = QuantumCircuit(*circuit.qregs, *circuit.cregs)
    for gate in circuit.data:
        if gate[0].name == 'cswap' or gate[0].name == 'cz':
            new_circuit.data.append(gate)
    return new_circuit.depth()

def swap_depth(circuit):
    new_circuit = QuantumCircuit(*circuit.qregs, *circuit.cregs)
    for gate in circuit.data:
        if gate[0].name == 'swap' or gate[0].name == 'cz': 
            new_circuit.data.append(gate)
    return new_circuit.depth()        
            