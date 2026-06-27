from .Metrics import Metric
from .feature import Circuitfeature
from qiskit_ibm_runtime import IBMBackend
from qiskit.providers.fake_provider import FakeBelem
class QPU(Metric):
    def __init__(self,width,backend:IBMBackend=None) -> None:
        self.width = width
        if backend:
            self.backend = backend
        else:
            self.backend = FakeBelem()
        super().__init__(self.backend)
    def get_circuit_feature(self,circuit):
        return Circuitfeature(circuit,self.backend)
    @property
    def adj(self):
        from numpy import zeros
        num_qubits = self.backend.num_qubits if hasattr(self.backend, "num_qubits") else self.backend.configuration().num_qubits
        vector = zeros((num_qubits,num_qubits))
        for gate in self.backend.configuration().coupling_map:
            vector[gate[0],gate[1]] = 1
        return vector
