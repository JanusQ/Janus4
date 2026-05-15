## using pennylane implement the bucket brigade qram
import pennylane as qml
from pennylane import numpy as np
import math
from typing import Iterable,List,Union
class routerQubit:
    def __init__(self,index,level):
        self.index = index
        self.level = level
        self.left = None
        self.right = None
        self.left_router = None
        self.right_router = None
        self.direction = ''
        self.root = None
    @property
    def address(self):
        if self.root == None:
            return self.direction
        else:
            return self.root.address+self.direction

class Qram:
    def __init__(self, address, data,bandwidth=1):
        self.address = address
        self.data = data
        self.bandwidth = bandwidth
        self.apply_classical_bit = True

    def generate_router_tree(self,level):
        router = routerQubit(self.cur_index,level)
        router.left = router.index+1
        router.right = router.index+2
        self.cur_index += 3
        if level == len(self.address_qubits)-1:
            self.routers[level].append(router)
            return router
        router.left_router = self.generate_router_tree(level+1)
        router.left_router.direction='0'
        router.left_router.root=router
        router.right_router = self.generate_router_tree(level+1)
        router.right_router.direction='1'
        router.right_router.root=router
        self.routers[level].append(router)
        return router

    def assign_qubits(self):
        self.incident_qubit_index = self.start_qubit_index
        self.cur_index = self.start_qubit_index +1
        self.routers = [[] for _ in self.address_qubits]
        self.generate_router_tree(0)

    def __call__(self,address_qubits:Iterable[int],bus_qubits:Iterable[int]):
        """call the QRAM 

        Args:
            address_qubits (Iterable[int]): the qubits used to represent the address 
            bus_qubits (Iterable[int]): the qubits for the bus
        """        
        self.busqubits = bus_qubits
        self.address_qubits = address_qubits
        self.start_qubit_index = max(self.busqubits+self.address_qubits)
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
            self.router(router.left_router.index,router.left,router.left_router.left,router.left_router.right)
        if router.right_router != None:
            next_routers.append((router.right_router,router.right))
            self.router(router.right_router.index,router.right,router.right_router.left,router.right_router.right)
        for next_router,_ in next_routers:
            self.router_to_bus(next_router)
        
        if router.left_router == None:
            if self.apply_classical_bit:
                # qml.RY(np.pi*self.data[int(router.address+'0',2)], wires=[router.left])
                qml.RZ(np.pi*self.data[int(router.address+'0',2)], wires=[router.left])
            else:
                qml.RY(self.data_amp[int(router.address+'0',2)], wires=[router.left])
                qml.RZ(self.data_phase[int(router.address+'0',2)], wires=[router.left])

        if router.right_router == None:
            ## apply the data to the left and right
            if self.apply_classical_bit:
                # qml.RY(np.pi*self.data[int(router.address+'1',2)], wires=[router.right])
                qml.RZ(np.pi*self.data[int(router.address+'1',2)], wires=[router.right])
            else:
                qml.RY(self.data_amp[int(router.address+'1',2)], wires=[router.right])
                qml.RZ(self.data_phase[int(router.address+'1',2)], wires=[router.right])
        # for next_router in next_routers:    
        #     # self.router_to_bus(next_router,incident)
        for next_router,incident in next_routers:
            self.reverse_router(next_router.index,incident,next_router.left,next_router.right)
        
        
    ## using pennylane implement the qram
    def decompose_circuit(self):
        for idx in self.busqubits:
            qml.Hadamard(wires=idx)
        for level in range(len(self.address_qubits)):
            for router in self.routers[level]:
                qml.CNOT(wires=[self.address_qubits[level],router.index])
        self.router(self.routers[0][0].index,self.busqubits[0],self.routers[0][0].left,self.routers[0][0].right)
        self.router_to_bus(self.routers[0][0])
        self.reverse_router(self.routers[0][0].index,self.busqubits[0],self.routers[0][0].left,self.routers[0][0].right)
        ## reverse the previous step
        for level in range(len(self.address_qubits)):
            for router in self.routers[level]:
                qml.CNOT(wires=[self.address_qubits[level],router.index])
        
        for idx in self.busqubits:
            qml.Hadamard(wires=idx)

def get_circuit(n_address_qubits: int, datacells: Union[List[float], List[int]], bandwidth: int):
    if not isinstance(datacells, Iterable):
        raise ValueError("Data must be a list of integers or floats.")
    address = [bin(i)[2:].zfill(n_address_qubits) for i in range(2**n_address_qubits)]
    if len(datacells)!= len(address):
        raise ValueError("Data must be the same length as the number of possible addresses.")
    return Qram(address,data,bandwidth=1)
    
    

if __name__ == "__main__":
    dev = qml.device("default.qubit", wires=30)
    address = [bin(i)[2:].zfill(3) for i in range(8)]
    data = [i/8 for i in range(8)]
    @qml.qnode(dev)
    def circuit(address,data):
        ## init the address
        qml.Hadamard(wires=0)
        qml.Hadamard(wires=1)
        Qram(address,data,bandwidth=1)([0,1,2],[3])
        return qml.expval(qml.PauliZ(3))
    ## draw the circuit
    print(qml.draw(circuit)(address,data))
    state = circuit(address,data)





