from typing import Any
import pennylane as qml
import numpy as np
class quantumwalkRAM:
    def __init__(self,data,address,dev,bandwidth=1) -> None:
        self.data = data
        self.address = address
        self.bandwidth = bandwidth
        self.dev = dev
        pass
    def init_space(self):
        self.busqubits = [i for i in range(self.bandwidth)]
        self.addressqubits = [i for i in range(len(self.address))]
        self.bucketqubits = [i for i in range(len(self.data))]
        self.charityqubit = 0
        self.n = int(np.log2(len(self.address)))
    def S(self,w,l):
        ## shift unitary
        unitary = np.zeros((2**(self.n+1),2**(self.n+1)))
        for i in [0,1]:
            shift = np.zeros((2**self.n,2**self.n))
            shift[2*w+i][w] =1
            shift[w][2*w+i] =1
            dift = (1+(-1)**i)/2
            shift[2*w+dift][2*w+dift] =1
            charity = np.zeros((2,2))
            charity[i][i] = 1
            unitary += np.kron(shift,charity)
        return unitary
    def F(self,l):
        return np.sum(self.S(w,l) for w in range(2**l))
    def one_step_routing(self,l):
        ## from l =0 start 
        qml.CNOT([self.address[self.n-(l+1)],self.charityqubit])
        ## quantum walk by the charityqubit
        qml.QubitUnitary(self.F(l),wires=self.bucketqubits+[self.charityqubit])
        qml.CNOT([self.address[self.n-(l+1)],self.charityqubit])
    def one_step_routing_reverse(self,l):
        qml.CNOT([self.address[self.n-(l+1)],self.charityqubit])
        qml.QubitUnitary(self.F(l).conj().T,wires=self.bucketqubits+[self.charityqubit])
        qml.CNOT([self.address[self.n-(l+1)],self.charityqubit])
    def routing(self):
        for l in range(self.n):
            self.one_step_routing(l)
    def reverse_routing(self):
        for l in range(self.n-1,-1,-1):
            self.one_step_routing_reverse(l)
    def querying(self):
        for i in range(len(self.data)):
            if self.data[i]:
                qml.X(self.dataqubits[i])
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.init_space()
        self.routing()
        self.querying()
        self.reverse_routing()

    
