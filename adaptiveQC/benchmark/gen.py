import os
from qiskit import QuantumCircuit
def gen_data(md=5,path='./benchmarkRun'):
    for root, dirs, files in os.walk(path):
        for file in files:
            filepath = os.path.join(root, file)
            qc = QuantumCircuit.from_qasm_file(filepath)
            qc.remove_final_measurements()
            width = qc.width()
            yield {
                "name": file.split('_')[0],
                'circuit': qc,
                'width': width,
                'md': md
            }