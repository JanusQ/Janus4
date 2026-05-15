## using pennylane implement the bucket brigade qram
import pennylane as qml
from pennylane import numpy as np
import math

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
    
    def layers_router(self,routerobj,incident,address_index,mid):
        if routerobj.level ==0 :
            qml.SWAP(wires=[incident,mid])
        if routerobj.level ==0 and address_index == 0:
            qml.SWAP(wires=[routerobj.reg_name,mid])
        else:
            self.router(routerobj.reg_name,mid,routerobj.left,routerobj.right)
            if routerobj.level+1 == address_index:
                if routerobj.left_router != None:
                    qml.SWAP(wires=[routerobj.left_router.reg_name,routerobj.left])
                if routerobj.right_router != None:
                    qml.SWAP(wires=[routerobj.right_router.reg_name,routerobj.right])
                return 
            if routerobj.left_router != None:
                self.layers_router(routerobj.left_router,routerobj.left,address_index,routerobj.left)
            if routerobj.right_router != None:
                self.layers_router(routerobj.right_router,routerobj.right,address_index,routerobj.right)

    def reverse_layers_router(self,routerobj,incident,address_index,mid):
        
        if address_index != 0:
            if routerobj.level+1 > address_index:
                return
            if routerobj.right_router != None:
                self.reverse_layers_router(routerobj.right_router,routerobj.right,address_index,routerobj.right)
            if routerobj.left_router != None:
                self.reverse_layers_router(routerobj.left_router,routerobj.left,address_index,routerobj.left)
            if routerobj.level+1 == address_index:
                if routerobj.right_router != None:
                    qml.SWAP(wires=[routerobj.right_router.reg_name,routerobj.right])
                if routerobj.left_router != None:
                    qml.SWAP(wires=[routerobj.left_router.reg_name,routerobj.left])
            self.reverse_router(routerobj.reg_name,mid,routerobj.left,routerobj.right)

        else:
            qml.SWAP(wires=[routerobj.reg_name,mid])
        if routerobj.level ==0 :
            qml.SWAP(wires=[incident,mid])
        
    
    ## using pennylane implement the qram
    def decompose_circuit(self):
        input_qubit = "incident"
        for idx in self.busqubits:
            qml.Hadamard(wires=idx)
        incidents = self.address_qubits+self.busqubits
        for idx in range(len(self.address_qubits)+1):
            self.layers_router(self.routers[0][0],incidents[idx],idx,input_qubit)
        for routerobj in self.routers[-1]:
            if self.apply_classical_bit:
            ## apply the classical bit by classical control
                qml.RY(np.pi*self.data[int(routerobj.address+'0',2)], wires=[routerobj.left])
                qml.RY(np.pi*self.data[int(routerobj.address+'1',2)], wires=[routerobj.right])
            else:
                qml.RY(self.data_amp[int(routerobj.address+'0',2)], wires=[routerobj.left])
                qml.RZ(self.data_phase[int(routerobj.address+'0',2)], wires=[routerobj.left])
                qml.RY(self.data_amp[int(routerobj.address+'1',2)], wires=[routerobj.right])
                qml.RZ(self.data_phase[int(routerobj.address+'1',2)], wires=[routerobj.right])
        for idx in reversed(range(len(self.address_qubits)+1)):
            self.reverse_layers_router(self.routers[0][0],incidents[idx],idx,input_qubit)
        for idx in self.busqubits:
            qml.Hadamard(wires=idx)
        
        
if __name__ == "__main__":
    address = [bin(i)[2:].zfill(3) for i in range(8)]
    data = [i/8 for i in range(8)]
    address_qubits = [f'add_{i}' for i in range(2)]
    bus_qubits = ['bus_0']
    with qml.tape.QuantumTape() as circuit:
        ## init the address
        qml.Hadamard(wires=address_qubits[0])
        qml.Hadamard(wires=address_qubits[1])
        # qml.Hadamard(wires=address_qubits[2])
        Qram(address,data,bandwidth=1)(address_qubits,bus_qubits)
        qml.expval(qml.PauliZ(bus_qubits))
    dev = qml.device("default.qubit", wires=circuit.wires)
    print(circuit.draw())
    print(qml.execute([circuit], dev, gradient_fn=None))
    print(dev.state)





