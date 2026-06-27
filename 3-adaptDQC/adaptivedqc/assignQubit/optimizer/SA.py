import random
import math
from typing import Iterable
from qiskit import QuantumCircuit
from ..OBJ import DQCObj

def simulated_annealing(circuit: QuantumCircuit,optimize: str,initial_allocation: Iterable,qpu, starting_temperature: float=1000, cooling_rate: float=0.9, stopping_temperature: float=1):
    """Simulated annealing algorithm for the partitioning problem.

    Args:
        circuit (QuantumCircuit):  QuantumCircuit
        optimize (str):  the objective function to optimize, it can be DataFlux,Latency,Fidelity or QU
        initial_allocation (Iterable):  the initial allocation of the qubits the format is like [0,0,1,1,2,2,3,3],
        the first two qubits are allocated to the first QPU, the second two qubits are allocated to the second QPU, and so on.
        starting_temperature (float, optional):  the starting temperature. Defaults to 1000.
        cooling_rate (float, optional):  the cooling rate. Defaults to 0.9.
        stopping_temperature (float, optional):  the stopping temperature. Defaults to 1.
    """
    def OBJ(allocation, circuit):
        return DQCObj(circuit, allocation,qpu).get_obj_min(optimize)
    # Initialize the current allocation to the initial allocation.
    current_allocation = initial_allocation

    # Evaluate the initial allocation.
    current_obj = OBJ(current_allocation[:circuit.width()], circuit)

    # Initialize the best allocation and best objective value to the current allocation and objective value.
    best_allocation = current_allocation
    best_obj = current_obj

    # Set the initial temperature to the starting temperature.
    temperature = starting_temperature

    # Loop until the temperature drops below the stopping temperature.
    while temperature > stopping_temperature:
        print('--'*10+str("T = ")+str(temperature)+"--"*10)
        # Generate a new candidate allocation by randomly swapping the position of two qubits in the allocation.
        new_allocation = current_allocation.copy()
        i,j = random.sample(range(len(new_allocation)), 2)
        while current_allocation[i] == current_allocation[j]:
            i, j = random.sample(range(len(new_allocation)), 2)
        new_allocation[i], new_allocation[j] = new_allocation[j], new_allocation[i]
        
        # Evaluate the new allocation.
        new_obj = OBJ(new_allocation[:circuit.width()], circuit)

        # Calculate the probability of accepting the new allocation.
        delta_obj = new_obj - current_obj
        acceptance_prob = math.exp(-delta_obj / temperature)

        # If the new allocation is better, set it as the current allocation and update the best allocation.
        if delta_obj < 0:
            current_allocation = new_allocation
            current_obj = new_obj
            if new_obj < best_obj:
                best_allocation = new_allocation
                best_obj = new_obj
        # Otherwise, accept the new allocation with probability acceptance_prob.
        elif random.random() < acceptance_prob:
            current_allocation = new_allocation
            current_obj = new_obj
        print(current_allocation)
        # Decrease the temperature.
        temperature *= cooling_rate

    # Return the best allocation and best objective value.
    return best_allocation[:circuit.width()], best_obj
