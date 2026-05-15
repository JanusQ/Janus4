from qiskit import QuantumCircuit, transpile, QuantumRegister, ClassicalRegister
from qiskit_aer import Aer
from qiskit.circuit.library import RYGate, RZGate
import numpy as np

class RouterQubit:
    def __init__(self, index, level, direction, root, is_leaf=False):
        self.index = index
        self.level = level
        self.root = root
        self.left_router = None
        self.right_router = None
        self.direction = direction
        if is_leaf:
            self.datareg = None
            self.qreg = QuantumRegister(1,f'datacell_{level}_{self.address}')
        else:
            self.datareg = QuantumRegister(1, name=f"data_{self.reg_name}")
            self.qreg = QuantumRegister(1,self.reg_name)

    def add_data(self):
        self.left_router = RouterQubit(self.index, self.level + 1, '0', self, is_leaf=True)
        self.right_router = RouterQubit(self.index, self.level + 1, '1', self, is_leaf=True)
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

class Qram:
    def __init__(self, address, data, bandwidth=1):
        self.address = address
        self.data = data
        self.bandwidth = bandwidth
        self.apply_classical_bit = True

    def generate_router_tree(self, level, direction, root, circuit:QuantumCircuit):
        router = RouterQubit(self.cur_index, level, direction, root)
        circuit.add_register(router.qreg)
        circuit.add_register(router.datareg)
        self.cur_index += 1
        if level == len(self.address_qubits) - 1:
            router.add_data()
            circuit.add_register(router.left_router.qreg)
            circuit.add_register(router.right_router.qreg)
            self.routers[level].append(router)
            return router
        router.left_router = self.generate_router_tree(level + 1, '0', router, circuit)
        router.right_router = self.generate_router_tree(level + 1, '1', router, circuit)
        self.routers[level].append(router)
        return router

    def assign_qubits(self,circuit):
        self.cur_index = 0
        self.routers = [[] for _ in self.address_qubits]
        self.generate_router_tree(0, '', None,circuit)

    def __call__(self,circuit, address_qubits, bus_qubits):
        
        self.address_qubits = address_qubits
        self.bus_qubits = bus_qubits
        self.assign_qubits(circuit)
        self.decompose_circuit(circuit)

        return circuit
    def router(self, circuit, router, incident, left, right):
        circuit.x(router)
        circuit.cswap(router, incident, left)
        circuit.x(router)
        circuit.cswap(router, incident, right)
    def reverse_router(self, circuit, router, incident, left, right):
        circuit.cswap(router, incident, right)
        circuit.x(router)
        circuit.cswap(router, incident, left)
        circuit.x(router)

    def layers_router(self, circuit, router_obj, incident, address_index):
        if router_obj.level == 0 and address_index == 0:
            circuit.swap(router_obj.qreg, incident)
        else:
            if router_obj.left_router is not None and router_obj.right_router is not None:
                if router_obj.level + 1 == address_index:
                    self.router(circuit, router_obj.qreg, incident, router_obj.left_router.qreg, router_obj.right_router.qreg)
                    return
                else:
                    self.router(circuit, router_obj.qreg, incident, router_obj.left_router.datareg, router_obj.right_router.datareg)
            if router_obj.left_router is not None:
                self.layers_router(circuit, router_obj.left_router, router_obj.left_router.datareg, address_index)
            if router_obj.right_router is not None:
                self.layers_router(circuit, router_obj.right_router, router_obj.right_router.datareg, address_index)

    def reverse_layers_router(self, circuit, router_obj, incident, address_index):
        if address_index != 0:
            if router_obj.level + 1 > address_index:
                return
            if router_obj.right_router is not None:
                self.reverse_layers_router(circuit, router_obj.right_router, router_obj.right_router.datareg, address_index)
            if router_obj.left_router is not None:
                self.reverse_layers_router(circuit, router_obj.left_router, router_obj.left_router.datareg, address_index)
            if router_obj.left_router is not None and router_obj.right_router is not None:
                if router_obj.level + 1 == address_index:
                    self.router(circuit, router_obj.qreg, incident, router_obj.left_router.qreg, router_obj.right_router.qreg)
                    return
                else:
                    self.router(circuit, router_obj.qreg, incident, router_obj.left_router.datareg, router_obj.right_router.datareg)
        if router_obj.level == 0:
            circuit.swap(incident, router_obj.qreg)

    def decompose_circuit(self, circuit):
        for idx in self.bus_qubits:
            circuit.h(idx)
        incidents = {i:self.address_qubits[i] for i in range(self.address_qubits._size)}
        incidents.update({i+self.address_qubits._size:self.bus_qubits[i] for i in range(self.bus_qubits._size)})
        for idx in range(len(incidents)):
            self.layers_router(circuit, self.routers[0][0], incidents[idx], idx)
            circuit.barrier()
        for router_obj in self.routers[-1]:
            if self.apply_classical_bit:
                circuit.ry(np.pi * self.data[int(router_obj.address + '0', 2)], router_obj.left_router.qreg)
                circuit.ry(np.pi * self.data[int(router_obj.address + '1', 2)], router_obj.right_router.qreg)
            else:
                circuit.append(RYGate(self.data[int(router_obj.address + '0', 2)]), [router_obj.left_router.qreg])
                circuit.append(RZGate(self.data[int(router_obj.address + '0', 2)]), [router_obj.left_router.qreg])
                circuit.append(RYGate(self.data[int(router_obj.address + '1', 2)]), [router_obj.right_router.qreg])
                circuit.append(RZGate(self.data[int(router_obj.address + '1', 2)]), [router_obj.right_router.qreg])
        circuit.barrier()
        for idx in reversed(range(len(self.address_qubits) + 1)):
            self.reverse_layers_router(circuit, self.routers[0][0], incidents[idx], idx)
            circuit.barrier()
        for idx in self.bus_qubits:
            circuit.h(idx)

if __name__ == "__main__":
    address = [bin(i)[2:].zfill(2) for i in range(8)]
    print(address)
    # data = [i / 8 for i in range(8)]
    data = [0,1,0,1,0,1,0,1]
    address_qregs = QuantumRegister(3, 'address')
    bus_qregs = QuantumRegister(1, 'bus')
    bus_cregs = ClassicalRegister(1, 'bus_classical')
    circuit = QuantumCircuit(address_qregs, bus_qregs, bus_cregs)
    circuit.x(address_qregs[0])
    # circuit.x(address_qregs[1])
    # circuit.x(address_qregs[2])
    qram = Qram(address, data, bandwidth=1)
    qram(circuit,address_qregs, bus_qregs)
    circuit.measure(bus_qregs,bus_cregs)
    print(circuit)
    print(circuit.num_qubits)
    print(circuit.depth())
    circuit.draw(output='mpl', filename='circuit.png')
    # transpiled_circuit = transpile(circuit, basis_gates=['rz','h','cz'], coupling_map=[[]])
    simulator = Aer.get_backend('qasm_simulator')
    result = simulator.run(transpile(circuit, simulator)).result()
    counts = result.get_counts(circuit)
    print(counts)
