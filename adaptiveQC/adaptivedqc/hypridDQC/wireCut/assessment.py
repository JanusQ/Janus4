
import numpy as np
from ...assessment import QPU,Metric
from ...assessment.feature import Circuitfeature
class AssessModel:
    def __init__(self,solution,qubits,qpu:QPU) -> None:
        for field in solution:
            self.__setattr__(field, solution[field])
        self._qargs = qubits
        self.metric= qpu
        self.width = len(qubits)
        # self.DataFlux = self.DataFlux()
        # self.Latency = self.Latency()
        self.Fidelity = self.Fidelity()
        # self.QU = self.QU()
    def _shot(self,basicshot:int,epsilon):
        return basicshot* 2**(4*self.num_cuts)/epsilon**2
    
    def DataFlux(self):
        data =0
        for idx in range(len(self.counter)):
            data+= 4**(self.counter[idx]["O"]+self.counter[idx]["rho"])
            if data > 2*20:
                break
        return data
    def Latency(self):
        latency = []
        for item in self.latency:
            latency.append(max(item.values()))
        return max(latency)
    
    def _Latency(self,classicalUnitTime=1):
        quantumtime = 0
        classicaltime = 0
        for index,_ in enumerate(self.subcircuits):
            quantumtime += 4**(self.counter[index]["rho"]+self.counter[index]["O"])*self._shot(1000,0.33)*max(self.latency[index].values())
        for q in self._qargs:
            classicaltime += 4**(len(self.complete_path_map[q])-1)
        classicaltime*= classicalUnitTime
        self.quantumtime = quantumtime
        self.classicaltime = classicaltime
        return classicaltime+quantumtime
    
    def Fidelity(self):
        fidelities = []
        comp = self.complete_path_map
        for q in comp:
            qfide = 1
            for path in comp[q]:
                qfide*=(1-self.error[path["subcircuit_idx"]][path['subcircuit_qubit']])*(1-self.metric.measurement_error(path['subcircuit_qubit']))
            fidelities.append(qfide)
        self.qfidelity = fidelities
        return np.prod(fidelities)
    
    def QU(self):
        qu = 0
        for i,subcir in enumerate(self.subcircuits):
            qu+=Circuitfeature(subcir).qubit_utilizztion
        return qu/(i+1)
