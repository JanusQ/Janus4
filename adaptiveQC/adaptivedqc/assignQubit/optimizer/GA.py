import random
from typing import Iterable
from ..OBJ import DQCObj
from qiskit.circuit import QuantumCircuit


def create_initial_population(n_population,initial_allocation):
    # Initialize the initial population of qubit allocations.
    # Replace this with your own initialization strategy if needed.
    population = []
    for i in range(n_population):
        random.shuffle(initial_allocation)
        population.append(initial_allocation)
    return population


def select_parents(population, tournament_size,OBJ):
    # Tournament selection: randomly select tournament_size individuals and return the best.
    parents = []
    for i in range(2):
        candidates = random.sample(population, tournament_size)
        best = min(candidates, key=lambda x: OBJ(x))
        parents.append(best)
    return parents


def crossover(parents):
    # Two-point crossover: randomly select two crossover points and exchange the genes between them.
    parent1, parent2 = parents
    n = len(parent1)
    point1, point2 = sorted(random.sample(range(n), 2))
    child1 = parent1[point1:point2]
    child2 = parent2[point1:point2]
    for i in range(n):
        if point1 <= i < point2:
            continue
        gene = parent1[i]
        if gene not in child2:
            child2.append(gene)
        else:
            j = parent2.index(gene)
            while j in range(point1, point2):
                j = parent2.index(parent1[j])
            child2.append(parent2[j])
        gene = parent2[i]
        if gene not in child1:
            child1.append(gene)
        else:
            j = parent1.index(gene)
            while j in range(point1, point2):
                j = parent1.index(parent2[j])
            child1.append(parent1[j])
    return child1, child2


def mutate(allocation, mutation_rate):
    # Swap mutation: randomly swap two genes with a probability of mutation_rate.
    for i in range(len(allocation)):
        if random.random() < mutation_rate:
            j = random.randint(0, len(allocation) - 1)
            allocation[i], allocation[j] = allocation[j], allocation[i]
    return allocation


def genetic_algorithm(circuit: QuantumCircuit, optimize: str, initial_allocation: Iterable,qpu, n_population: int, tournament_size: int, crossover_rate: float, mutation_rate: float, n_generations: int):
    """ To use this genetic algorithm, you can call the `genetic_algorithm` function with the following arguments:
        - `circuit`: the quantum circuit to be optimized.
        - `optimize`: the objective function to be optimized, it can be DataFlux,Latency,Fidelity or QU.
        - `n_population`: the size of the population.
        - `tournament_size`: the number of individuals to consider in each tournament during parent selection.
        - `crossover_rate`: the probability of performing crossover.
        - `mutation_rate`: the probability of performing mutation.
        - `n_generations`: the number of generations to evolve the population.

        For example, to run the genetic algorithm with a population size of 100, 10 qubits, tournament size of 5, crossover rate of 0.8, mutation rate of 0.1, and 50 generations, you can call:

        ```python
        best_allocation =  genetic_algorithm(circuit, 'DataFlux', 100, 5, 0.8, 0.1, 50)
    Returns:
        List: best_allocation
    """
    n_qubits = circuit.width()
    def OBJ(allocation):
        return DQCObj(circuit, allocation[:n_qubits],qpu).get_obj_min(optimize)
    population = create_initial_population(n_population, initial_allocation)

    # Evolve the population for n_generations.
    for i in range(n_generations):
        print('Generation', i, 'best', OBJ(min(population, key=lambda x: OBJ(x))))
        # Select the parents.
        parents = select_parents(population, tournament_size,OBJ)

        # Apply crossover to create the offspring.
        if random.random() < crossover_rate:
            offspring = crossover(parents)
        else:
            offspring = parents

        # Apply mutation to the offspring.
        offspring = [mutate(allocation, mutation_rate)
                     for allocation in offspring]
        # Replace the worst individuals in the population with the offspring.
        combined_population = population + offspring
        fitness = [OBJ(allocation) for allocation in combined_population]
        indices = sorted(range(len(combined_population)),
                         key=lambda x: fitness[x])[:n_population]
        population = [combined_population[i] for i in indices]
    # Return the best individual found in the final population.

    # Return the best solution found.
    return min(population, key=lambda x: OBJ(x))


if __name__ == '__main__':
    print(crossover([[0,0,0, 1,1,1], [0,0,1,1,1,0]]))