from cpflow import *
import numpy as np
u_target = np.array([[0, 0, 0, 1],
                     [0, 1, 0, 0],
                     [0, 0, 1, 0],
                     [1, 0, 0, 0]])
layer = [[0, 1]]  # Linear connectivity
decomposer = Synthesize(layer, target_unitary=u_target, label='cswap')
options = StaticOptions(num_cp_gates=10, accepted_num_cz_gates=3, num_samples=20, target_loss=1e-8,rotation_gates='x')
results = decomposer.static(options) # Should take from one to five minutes.

d = results.decompositions[-2]  # This turned out to be the best decomposition for refinement.
d.refine()
print(d)
print(d.circuit.draw())