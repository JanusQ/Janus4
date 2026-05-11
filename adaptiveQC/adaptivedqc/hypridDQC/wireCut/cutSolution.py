class Solution:
    def __init__(self,name,solution_dict) -> None:
        self.solution=solution_dict
        self.name = name
        for key in solution_dict:
            setattr(self,key,solution_dict[key])
    def __str__(self) -> str:
        return self.print_solution()
    
    def print_solution(self):
        print("<"*20,self.name+" run result",">"*20)
        print("-" * 20)
        num_cuts=self.solution["num_cuts"]
        subcircuits=self.solution["subcircuits"]
        counter=self.solution["counter"]
        print("%d subcircuits, %d cuts" % (len(subcircuits), num_cuts))

        for subcircuit_idx in range(len(subcircuits)):
            print('>'*10,"subcircuit %d" % subcircuit_idx,'<'*10)
            print(
                "\u03C1 qubits = %d, O qubits = %d, width = %d, effective = %d, depth = %d, size = %d"
                % (
                    counter[subcircuit_idx]["rho"],
                    counter[subcircuit_idx]["O"],
                    counter[subcircuit_idx]["d"],
                    counter[subcircuit_idx]["effective"],
                    counter[subcircuit_idx]["depth"],
                    counter[subcircuit_idx]["size"],
                )
            )
            print(subcircuits[subcircuit_idx])
            print('-'*30)
        print('-'*40)
        return " "
    def Index_solution(self):
        pass
    def saveBins(self,approximation_bins):
        self.approximation_bins = approximation_bins
        self.qubits_prob = get_qubits_prob(approximation_bins)
        pass


def get_qubits_prob(arr):
    qubitsNum = len(bin(len(arr)))-3
    q= [[0,0] for i in range(qubitsNum)]
    for n in range(qubitsNum):
        for i in range(len(arr)):
            q[n][(2**n & i)>>n] += arr[i]
    return q
def get_bit_error(real,ideal):
    qubitsNum = len(bin(len(real)))-3
    q = get_qubits_prob(real)
    q_ideal = get_qubits_prob(ideal)
    return [abs(q[i][0]-q_ideal[i][0]) for i in range(qubitsNum)]
def get_qubits_error(res):
    real,ideal = res['real'],res['ideal']
    return get_bit_error(real,ideal)
