import pandas as pd
import pickle
import os
import re
import numpy as np
class AssessModel:
    def __init__(self,solution) -> None:
        for field in solution:
            self.__setattr__(field, solution[field])
        self._qargs = list(self.complete_path_map.keys())
        self.width = len(self._qargs)
        self.DataFlux = self.DataFlux()
        self.Latency = self.Latency()
        self.Fidelity = self.Fidelity()
        self.min_latency = self.min_latency()
        self.QU = self.QU()
    def DataFlux(self):
        data =0
        for idx in range(len(self.counter)):
            data+= 4**(self.counter[idx]["O"]+self.counter[idx]["rho"])
            if data>=2*20:
                break
        return data
    def min_latency(self):
        latency = []
        for item in self.latency:
            latency.append(max(item.values()))
        return min(latency)
    
    def Latency(self):
        latency = []
        for item in self.latency:
            latency.append(max(item.values()))
        return max(latency)

    def QU(self):
        rate = 1
        for item in self.latency:
            lats = item.values()
            rate*= sum(lats)/(max(lats)*len(lats))
        return rate
    def Fidelity(self):
        fidelity = 1
        comp = self.complete_path_map
        measurement_error = 0.001
        for  q in comp:
            qfide = 1
            for path in comp[q]:
                qfide*=(1-self.error[path["subcircuit_idx"]][path['subcircuit_qubit']])
                qfide*= (1-measurement_error)
            fidelity*=qfide
        return fidelity

def load_dict(name ):
    with open(name, 'rb') as f:
        return pickle.load(f)
def caculate_metrics():
    path = './data/'
    for root,dirs,files in os.walk(path):
        for file in files:
            Data_dict = {}
            filepath = os.path.join(root,file)
            if file.endswith('solution.pkl'):
                print(filepath)
                type = file.split('_')[-2]
                Data_dict['qpu_width']= int(re.sub('\D','',file.split('_')[0]))
                Data_dict['name'] = root.split('/')[-1]
                solution = load_dict(filepath)
                Data_dict[type+'_num_cuts'] = solution['num_cuts']
                Data_dict[type+'_subcircuits_num'] = solution['subcircuits_num']
                solution = AssessModel(solution)
                Data_dict[type+'_DataFlux'] = solution.DataFlux
                Data_dict[type+'_Latency'] = solution.Latency
                Data_dict[type+'_Fidelity'] = solution.Fidelity
                Data_dict[type+'_min_latency'] = solution.min_latency
                Data_dict[type+'_QU'] = solution.QU
                yield Data_dict

Metric_df = pd.DataFrame(list(caculate_metrics()))
Metric_df.to_csv('Metric_new.csv',index=False)