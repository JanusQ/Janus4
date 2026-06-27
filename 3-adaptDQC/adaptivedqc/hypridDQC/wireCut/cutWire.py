from .cutter import Cluster,MIP_Model 
from qiskit.converters import circuit_to_dag
from time import perf_counter
from .cutter.mip import find_cuts
from .cutter.post_process import  generate_subcircuit_entries,generate_compute_graph
from .excute import attribute_shots,run_subcircuit_instances,evaluate_circ
import os
from .bulid import DynamicDefinition,full_verify
from ...assessment import QPU
from .assessment  import AssessModel
def add_times(times_a, times_b):
    """
    Add the two time breakdowns
    """
    for field in times_b:
        if field in times_a:
            times_a[field] += times_b[field]
        else:
            times_a[field] = times_b[field]
    return times_a

class CutWire:
    def __init__(self,circuit,name,qpu:QPU,verbose:bool = False,data_folder:str="./data/temp") -> None:

        self.circuit = self.processCircuit(circuit)
        self.name = name
        # self.check_valid()
        self.qpu = qpu
        self.solution = {}
        self.times = {}
        self.verbose = verbose
        self.tmp_data_folder = data_folder
        os.makedirs(self.tmp_data_folder,exist_ok=True)
    
    def processCircuit(self,circuit):
        """
        If the input circuit is not fully connected, it does not need CutQC to be split into smaller circuits.
        CutQC hence only cuts a circuit if it is fully connected.
        Furthermore, CutQC only supports 2-qubit gates.
        """
        if circuit.num_unitary_factors() != 1:
            raise ValueError(
                "Input circuit is not fully connected thus does not need cutting. Number of unitary factors = %d"
                % circuit.num_unitary_factors()
            )
        dag = circuit_to_dag(circuit)
        for op_node in dag.topological_op_nodes():
            if len(op_node.qargs) > 2:
                raise ValueError("CutWire currently does not support >2-qubit gates")
            if op_node.op.name == "barrier":
                raise ValueError("Please remove barriers from the circuit before cutting")
        circuit.remove_final_measurements()
        if hasattr(circuit, "remove_barriers"):
            circuit.remove_barriers()
        return circuit
    
    def _generate_metadata(self):
        self.compute_graph = generate_compute_graph(
            counter=self.solution.counter,
            subcircuits=self.solution.subcircuits,
            complete_path_map=self.solution.complete_path_map,
        )

        (
            self.subcircuit_entries,
            self.subcircuit_instances,
        ) = generate_subcircuit_entries(compute_graph=self.compute_graph)
        if self.verbose:
            print("--> %s subcircuit_entries:" % self.name)
            for subcircuit_idx in self.subcircuit_entries:
                print(
                    "Subcircuit_%d has %d entries"
                    % (subcircuit_idx, len(self.subcircuit_entries[subcircuit_idx]))
                )

    def cluster_cut(self, goal=None):
        clus = Cluster(self.circuit)
        return clus.get_basic_solution(self.qpu)
    def adaptive_cut(self,goal='error'):
        clus = Cluster(self.circuit)
        return clus.get_solution(self.qpu,opt_type=goal)


    def print_info(self):
        print("-"*20,'Adaptive parting quantum circuit',"-"*20)
        print('PARTITION INFO:')
        print(
                "<-- QuantumCircuit:    name= %s width = %d depth = %d size = %d -->"
                % (
                    self.circuit.name,
                    self.circuit.num_qubits,
                    self.circuit.depth(),
                    self.circuit.num_nonlocal_gates(),
                )
            )
        print(
                "<-- QuantumProcessor Info:   width = %d -->"
                % (
                    self.qpu.width,
                )
            )
        print('>'*40)

    
    def mip_cut(self):
        """
        Cut the given circuits
        If use the MIP solver to automatically find cuts, the following are required:
        max_subcircuit_width: max number of qubits in each subcircuit

        The following are optional:
        max_cuts: max total number of cuts allowed
        num_subcircuits: list of subcircuits to try, CutQC returns the best solution found among the trials
        max_subcircuit_cuts: max number of cuts for a subcircuit
        max_subcircuit_size: max number of gates in a subcircuit
        quantum_cost_weight: quantum_cost_weight : MIP overall cost objective is given by
        quantum_cost_weight * num_subcircuit_instances + (1-quantum_cost_weight) * classical_postprocessing_cost

        Else supply the subcircuit_vertices manually
        Note that supplying subcircuit_vertices overrides all other arguments
        """
        if self.basic_solution:
            max_cuts =  self.basic_solution.num_cuts
            sub_num =self.basic_solution.subcircuits_num
            num_subs = list(range(max(2,sub_num-2),sub_num+2))
        self.cutter_constraints={
            "max_subcircuit_width": self.qpu.width,
            "max_subcircuit_cuts": max_cuts,
            "subcircuit_size_imbalance": 2,
            "max_cuts":max_cuts+2,
            "num_subcircuits": num_subs,
        }
        if self.verbose:
            print("*" * 20, "MIP Cut Start %s" % self.name, "*" * 20)
            print(self.cutter_constraints)
        cut_solution = find_cuts(
            **self.cutter_constraints, circuit=self.circuit, verbose=self.verbose
        )
        if cut_solution:
            latency = []
            error = []

            for subcir in cut_solution['subcircuits']:
                feature = self.qpu.get_feature(subcir)
                latency.append(feature._latency)
                error.append(feature._error)
            cut_solution['latency'] = latency
            cut_solution['error'] = error
        return cut_solution
    
    def assessment_dqc(self):
        ass = AssessModel(self.solution.solution,self.circuit.qubits,qpu)
        return ass
    
    ## run circuit
    def run_cut_circuit(self,goal=None,eval_mode='IBMRuntime',recursion_depth=4):
        start_time = perf_counter()
        if goal:
            print("*"*20,f"Adaptive cluster running with goal {goal}","*"*20)
            self.solution = self.adaptive_cut(goal)
            self.times['cutter']  = perf_counter()-start_time
        else:
            print("*"*20,"basic cluster running","*"*20)
            self.basic_solution = self.cluster_cut(goal)
            self.solution = self.basic_solution
            self.times['cutter']  = perf_counter()-start_time
        self._generate_metadata()
        self.evaluate(eval_mode= eval_mode, num_shots_fn=None)
        self.build(mem_limit=32, recursion_depth=recursion_depth)
        print("Cut: %d recursions." % (self.num_recursions))
        print("spend time",self.times)
        print("cut circuit approximation_bins:",self.approximation_bins)
        self.solution.saveBins(self.approximation_bins)  
        self.clean_data()
        return self.solution
    
    def evaluate(self, eval_mode, num_shots_fn):
        """
        eval_mode = qasm: simulate shots
        eval_mode = sv: statevector simulation
        num_shots_fn: a function that gives the number of shots to take for a given circuit
        """
        if self.verbose:
            print("*" * 20, "evaluation mode = %s" % (eval_mode), "*" * 20)
        self.eval_mode = eval_mode
        self.num_shots_fn = num_shots_fn

        evaluate_begin = perf_counter() 
        self._run_subcircuits()
        self._attribute_shots()
        self.times["evaluate"] = perf_counter() - evaluate_begin
        if self.verbose:
            print("evaluate took %e seconds" % self.times["evaluate"])

    def build(self, mem_limit, recursion_depth):
        """
        mem_limit: memory limit during post process. 2^mem_limit is the largest vector
        """
        if self.verbose:
            print("--> Build %s" % (self.name))

        # Keep these times and discard the rest
        self.times = {
            "cutter": self.times["cutter"],
            "evaluate": self.times["evaluate"],
        }

        build_begin = perf_counter()
        dd = DynamicDefinition(
            compute_graph=self.compute_graph,
            data_folder=self.tmp_data_folder,
            num_cuts=self.solution.num_cuts,
            mem_limit=mem_limit,
            recursion_depth=recursion_depth,
        )
        dd.build()

        self.times = add_times(times_a=self.times, times_b=dd.times)
        self.approximation_bins = dd.dd_bins
        self.num_recursions = len(self.approximation_bins)
        self.overhead = dd.overhead
        self.times["build"] = perf_counter() - build_begin
        self.times["build"] += self.times["cutter"]
        self.times["build"] -= self.times["merge_states_into_bins"]

        if self.verbose:
            print("Overhead = {}".format(self.overhead))

    def verify(self):
        verify_begin = perf_counter()
        reconstructed_prob, self.approximation_error = full_verify(
            full_circuit=self.circuit,
            complete_path_map=self.complete_path_map,
            subcircuits=self.subcircuits,
            dd_bins=self.approximation_bins,
        )
        self.times["verify"] = perf_counter() - verify_begin
        print("verify took %.3f s" % (self.times["verify"]))
        

    def clean_data(self):
        import shutil
        shutil.rmtree(self.tmp_data_folder)

    def _run_subcircuits(self):
        """
        Run all the subcircuit instances
        subcircuit_instance_probs[subcircuit_idx][(init,meas)] = measured prob
        """
        if self.verbose:
            print("--> Running Subcircuits %s" % self.name)
        self.clean_data()
        os.makedirs(self.tmp_data_folder,exist_ok=True)
        self.times["run_subcircuits"]=run_subcircuit_instances(
            subcircuits=self.solution.subcircuits,
            subcircuit_instances=self.subcircuit_instances,
            eval_mode=self.eval_mode,
            num_shots_fn=self.num_shots_fn,
            data_folder=self.tmp_data_folder,
        )
        print("run_subcircuits took",self.times["run_subcircuits"])

    def _attribute_shots(self):
        """
        Attribute the subcircuit_instance shots into respective subcircuit entries
        subcircuit_entry_probs[subcircuit_idx][entry_init, entry_meas] = entry_prob
        """
        if self.verbose:
            print("--> Attribute shots %s" % self.name)
        attribute_shots(
            subcircuit_entries=self.subcircuit_entries,
            subcircuits=self.solution.subcircuits,
            eval_mode=self.eval_mode,
            data_folder=self.tmp_data_folder,
        )

if __name__ == "__main__":
    seed = 0
    import numpy as np
    import random
    from qiskit import QuantumCircuit

    np.random.seed(seed)
    random.seed(seed)
    ## generate random circuit
    n_qubits = 5
    n_gates = 10
    circuit = QuantumCircuit(n_qubits)
    for i in range(n_gates):
        circuit.h(random.randint(0,n_qubits-1))
        ## 防止相同的比特作为控制比特
        control = random.randint(0,n_qubits-1)
        target = random.randint(0,n_qubits-1)
        while control == target:
            target = random.randint(0,n_qubits-1)
        circuit.cx(control,target)
    qpu = QPU(3)
    Adap = CutWire(circuit,'random',qpu,verbose=True)
    Adap.run_cut_circuit(type="cluster",goal='basic')
    # print(Adap.run_full_circuits("sv"))
    print(Adap.times)
    print(Adap.approximation_bins)
