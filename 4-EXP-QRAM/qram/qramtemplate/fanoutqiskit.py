from typing import Iterable, List, Union
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

class routerQubit:
    def __init__(self, index, level):
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
        if self.root is None:
            return self.direction
        else:
            return self.root.address + self.direction

class Qram:
    def __init__(self, address, data, bandwidth=1):
        self.address = address
        self.data = data
        self.bandwidth = bandwidth
        self.apply_classical_bit = True

    def generate_router_tree(self, level, direction='0', root=None):
        router = routerQubit(self.cur_index, level)
        if direction is not None:
            router.direction = direction
        if root is not None:
            router.root = root
        self.qr_routers_level.append(QuantumRegister(1,name=r'R_{}'.format(router.address)))
        self.cur_index += 1
        router.left = self.cur_index
        self.qr_routers_level.append(QuantumRegister(1,name=r'R_'+str(router.address)+'^l'))
        self.cur_index += 1
        router.right = self.cur_index
        self.qr_routers_level.append(QuantumRegister(1,name=r'R_'+str(router.address)+'^r'))
        self.cur_index += 1
        if level == self.n_address_qubits - 1:
            self.routers[level].append(router)
            return router
        router.left_router = self.generate_router_tree(level + 1, direction='0', root=router)
        router.right_router = self.generate_router_tree(level + 1
                                                        , direction='1', root=router)
        self.routers[level].append(router)
        return router

    def assign_qubits(self):
        self.n_address_qubits = len(self.address[0])
        self.n_bus_qubits = self.bandwidth
        self.incident_qubit_index = 0
        self.cur_index = 0
        self.routers = [[] for _ in range(self.n_address_qubits)]
        self.qr_routers_level = []
        self.generate_router_tree(0)
        self.n_routers = self.cur_index
        self.qr_address = QuantumRegister(self.n_address_qubits, name='address')
        self.qr_bus = QuantumRegister(self.n_bus_qubits, name='bus')
        # self.qr_routers = QuantumRegister(self.n_routers, name='routers')
        self.cr_address = ClassicalRegister(self.n_address_qubits, name='c_address')
        self.cr_bus = ClassicalRegister(self.n_bus_qubits, name='c_bus')
        self.cr_routers = ClassicalRegister(self.n_routers, name='c_routers')
        self.qc = QuantumCircuit(self.qr_address, self.qr_bus, self.cr_address, self.cr_bus,*self.qr_routers_level)
        self.qr_routers = [qr[0] for qr in self.qr_routers_level]
        # self.qc.x(self.qr_address[0])
        

    def __call__(self):
        self.assign_qubits()
        self.decompose_circuit()
        return self.qc

    def router(self, router, incident, left, right):
        if isinstance(incident, int):
            incident = self.qr_routers[incident]
        self.qc.x(self.qr_routers[router.index])
        self.qc.cswap(self.qr_routers[router.index], incident, self.qr_routers[left])
        self.qc.x(self.qr_routers[router.index])
        self.qc.cswap(self.qr_routers[router.index], incident, self.qr_routers[right])

    def reverse_router(self, router, incident, left, right):
        if isinstance(incident, int):
            incident = self.qr_routers[incident]
        self.qc.cswap(self.qr_routers[router.index], incident, self.qr_routers[right])
        self.qc.x(self.qr_routers[router.index])
        self.qc.cswap(self.qr_routers[router.index], incident, self.qr_routers[left])
        self.qc.x(self.qr_routers[router.index])

    def router_to_bus(self, router):
        
        next_routers = []
        if router.left_router != None:
            next_routers.append((router.left_router,router.left))
            self.router(router.left_router,router.left,router.left_router.left,router.left_router.right)
        if router.right_router != None:
            next_routers.append((router.right_router,router.right))
            self.router(router.right_router,router.right,router.right_router.left,router.right_router.right)
        for next_router,_ in next_routers:
            self.router_to_bus(next_router)
        
        if router.left_router is None:
            if self.apply_classical_bit:
                if self.data[int(router.address + '0', 2)]:
                    self.qc.z(self.qr_routers[router.left])
            else:
                amp = self.data_amp[int(router.address + '0', 2)]
                phase = self.data_phase[int(router.address + '0', 2)]
                self.qc.ry(amp, self.qr_routers[router.left])
                self.qc.rz(phase, self.qr_routers[router.left])

        if router.right_router is None:
            if self.apply_classical_bit:
                if self.data[int(router.address + '1', 2)]:
                    self.qc.z(self.qr_routers[router.right])
            else:
                amp = self.data_amp[int(router.address + '1', 2)]
                phase = self.data_phase[int(router.address + '1', 2)]
                self.qc.ry(amp, self.qr_routers[router.right])
                self.qc.rz(phase, self.qr_routers[router.right])

        for next_router, incident in next_routers:
            self.reverse_router(next_router, incident, next_router.left, next_router.right)

    def decompose_circuit(self):
        for bus_qubit in range(self.n_bus_qubits):
            self.qc.h(self.qr_bus[bus_qubit])
        self.qc.h(self.qr_address[0])
        self.qc.cx(self.qr_address[0], self.qr_address[1])
        
        for level in range(self.n_address_qubits):
            for router in self.routers[level]:
                self.qc.cx(self.qr_address[level], self.qr_routers[router.index])
        self.router(self.routers[0][0],self.qr_bus[0],self.routers[0][0].left,self.routers[0][0].right)
        self.qc.rx(np.pi/3,self.qr_routers[self.routers[1][1].index])
        self.router_to_bus(self.routers[0][0])
        self.reverse_router(self.routers[0][0],self.qr_bus[0],self.routers[0][0].left,self.routers[0][0].right)
        for level in range(self.n_address_qubits):
            for router in self.routers[level]:
                self.qc.cx(self.qr_address[level], self.qr_routers[router.index])
        for bus_qubit in range(self.n_bus_qubits):
            self.qc.h(self.qr_bus[bus_qubit])
        self.qc.measure(self.qr_bus, self.cr_bus)
        self.qc.measure(self.qr_address, self.cr_address)
        

def gen_circuit(n_address_qubits: int, datacells: Union[List[float], List[int]], bandwidth: int):
    if not isinstance(datacells, Iterable):
        raise ValueError("Data must be a list of integers or floats.")
    address = [bin(i)[2:].zfill(n_address_qubits) for i in range(2 ** n_address_qubits)]
    if len(datacells) != len(address):
        raise ValueError("Data must be the same length as the number of possible addresses.")
    qram = Qram(address, datacells, bandwidth=bandwidth)
    return qram()

# 使用示例
if __name__ == "__main__":
    n_address_qubits = 2
    datacells = [i / 4 for i in range(4)]
    bandwidth = 1
    qc = gen_circuit(n_address_qubits, datacells, bandwidth)
    qc.draw('mpl').savefig('qram.png')