if __name__ == '__main__':
    import random
    from adaptivedqc import Adaptivedqc
    n_qubits = 9
    n_gates = 20
    circuit = Adaptivedqc(n_qubits,n_qubits)
    for i in range(n_gates):
        circuit.h(random.randint(0,n_qubits-1))
        ## 防止相同的比特作为控制比特
        control = random.randint(0,n_qubits-1)
        target = random.randint(0,n_qubits-1)
        while control == target:
            target = random.randint(0,n_qubits-1)
        circuit.cx(control,target)
    solution_circuit = circuit.run_on_part_qubits()
    print(solution_circuit)