
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

class QROM(QuantumCircuit):
    """采用比特数更少的版本模拟QRAM

    Args:
        QuantumCircuit (_type_): _description_
    """
    def __init__(self, address_size: int,data: list, bandwidth: int=1) -> None:
        self.address_size = address_size
        self.datacells_size = 2 ** address_size
        self.bandwidth = bandwidth
        assert len(data) == self.datacells_size, "Data size does not match address size"
        self.datacells = data
        self.qr_address = QuantumRegister(self.address_size, name='address')
        self.qr_bus = QuantumRegister(self.bandwidth, name='bus')
        self.cr_address = ClassicalRegister(self.address_size, name='c_address')
        self.cr_routers = ClassicalRegister(self.datacells_size, name='c_routers')
        super().__init__(self.qr_address, self.qr_bus, self.cr_address, self.cr_routers)
        self.build()
    

    def build(self) -> None:
        # Initialize bus qubit
        self.h(self.qr_bus[0])

        # Address states
        addresses = [format(i, f'0{self.address_size}b') for i in range(self.datacells_size)]
        # Write data to bus
        for i in range(self.datacells_size):
            # Set address 
            for j in range(self.address_size):
                if addresses[i][j] == '1':
                    self.x(self.qr_address[j])
            # Write data 
            if self.datacells[i]:
                # self.mcx(self.qr_address, self.qr_bus[0])
                self.mcp(self.datacells[i],self.qr_address, self.qr_bus[0])
            # Reset addresses
            for j in range(self.address_size):
                if addresses[i][j] == '1':
                    self.x(self.qr_address[j])
    def qubits_size(self):
        return self.address_size + self.bandwidth+ 3*(2**self.address_size-1)
    def gen_circuit(self):
        return self