## using pennylane implement the bucket brigade qram
import pennylane as qml
from pennylane import numpy as np

class routerQubit:
    def __init__(self,index,level,direction,root):
        self.index = index
        self.level = level
        self.root = root
        self.left_router = None
        self.right_router = None
        self.direction = direction
        self.left = self.reg_name + '_l'
        self.right = self.reg_name + '_r'
    @property
    def address(self):
        if self.root == None:
            return self.direction
        else:
            return self.root.address+self.direction
    @property
    def reg_name(self):
        if self.address != '':
            return f"router_{self.level}_{self.address}"
        else:
            return f"router_{self.level}"

class Qram:
    def __init__(self, address, data,bandwidth=1):
        self.address = address
        self.data = data
        self.bandwidth = bandwidth
        self.apply_classical_bit = True

    def generate_router_tree(self,level,direction,root):
        router = routerQubit(self.cur_index,level,direction,root)
        self.cur_index += 3
        if level == len(self.address_qubits)-1:
            self.routers[level].append(router)
            return router
        router.left_router = self.generate_router_tree(level+1,'0',router)
        router.right_router = self.generate_router_tree(level+1,'1',router)
        self.routers[level].append(router)
        return router

    def assign_qubits(self):
        self.incident_qubit_index = self.start_qubit_index
        self.cur_index = self.start_qubit_index +1
        self.routers = [[] for _ in self.address_qubits]
        self.generate_router_tree(0,'',None)

    def __call__(self,address_qubits,bus_qubits):
        self.busqubits = bus_qubits
        self.address_qubits = address_qubits
        self.start_qubit_index = 0
        self.assign_qubits()
        self.decompose_circuit()
        ## add the ancilla qubits
    def router(self,router,incident,left,right):
        qml.X(router)
        qml.CSWAP(wires=[router,incident,left])
        qml.X(router)
        qml.CSWAP(wires=[router,incident,right])
    def reverse_router(self,router,incident,left,right):
        qml.CSWAP(wires=[router,incident,right])
        qml.X(router)
        qml.CSWAP(wires=[router,incident,left])
        qml.X(router)
    def router_to_bus(self,router):
        next_routers = []
        if router.left_router != None:
            next_routers.append((router.left_router,router.left))
            self.router(router.left_router.reg_name,router.left,router.left_router.left,router.left_router.right)
        if router.right_router != None:
            next_routers.append((router.right_router,router.right))
            self.router(router.right_router.reg_name,router.right,router.right_router.left,router.right_router.right)
        for next_router,_ in next_routers:
            self.router_to_bus(next_router)
        
        if router.left_router == None:
            if self.apply_classical_bit:
                # qml.RY(np.pi*self.data[int(router.address+'0',2)], wires=[router.left])
                qml.RY(np.pi*self.data[int(router.address+'0',2)], wires=[router.left])
            else:
                qml.RY(self.data_amp[int(router.address+'0',2)], wires=[router.left])
                qml.RZ(self.data_phase[int(router.address+'0',2)], wires=[router.left])

        if router.right_router == None:
            ## apply the data to the left and right
            if self.apply_classical_bit:
                # qml.RY(np.pi*self.data[int(router.address+'1',2)], wires=[router.right])
                qml.RY(np.pi*self.data[int(router.address+'1',2)], wires=[router.right])
            else:
                qml.RY(self.data_amp[int(router.address+'1',2)], wires=[router.right])
                qml.RZ(self.data_phase[int(router.address+'1',2)], wires=[router.right])
        # for next_router in next_routers:    
        #     # self.router_to_bus(next_router,incident)
        for next_router,incident in reversed(next_routers):
            self.reverse_router(next_router.reg_name,incident,next_router.left,next_router.right)
        
        
    ## using pennylane implement the qram
    def decompose_circuit(self):
        for idx in self.busqubits:
            qml.Hadamard(wires=idx)
        for level in range(len(self.address_qubits)):
            for router in self.routers[level]:
                qml.CNOT(wires=[self.address_qubits[level],router.reg_name])
        self.router(self.routers[0][0].reg_name,self.busqubits[0],self.routers[0][0].left,self.routers[0][0].right)
        self.router_to_bus(self.routers[0][0])
        self.reverse_router(self.routers[0][0].reg_name,self.busqubits[0],self.routers[0][0].left,self.routers[0][0].right)
        ## reverse the previous step
        for level in reversed(range(len(self.address_qubits))):
            for router in reversed(self.routers[level]):
                qml.CNOT(wires=[self.address_qubits[level],router.reg_name])
        
        for idx in self.busqubits:
            qml.Hadamard(wires=idx)


if __name__ == "__main__":
    address = [bin(i)[2:].zfill(3) for i in range(8)]
    data = [i/8 for i in range(8)]
    address_qubits = [f'add_{i}' for i in range(3)]
    bus_qubits = ['bus_0']
    with qml.tape.QuantumTape() as circuit:
        ## init the address
        qml.Hadamard(wires=address_qubits[0])
        qml.Hadamard(wires=address_qubits[1])
        qml.Hadamard(wires=address_qubits[2])
        Qram(address,data,bandwidth=1)(address_qubits,bus_qubits)
        qml.expval(qml.PauliZ(bus_qubits))
    dev = qml.device("default.qubit", wires=circuit.wires)
    print(circuit.draw())
    print(qml.execute([circuit], dev, gradient_fn=None))
    print(dev.state)





