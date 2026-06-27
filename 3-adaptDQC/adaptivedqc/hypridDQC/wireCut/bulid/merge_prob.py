import argparse, pickle, itertools
import numpy as np

from ..excute.evaluate_circuit import find_process_jobs


def merge_prob_vector(unmerged_prob_vector, qubit_states):
    num_active = qubit_states.count("active")
    num_merged = qubit_states.count("merged")
    merged_prob_vector = np.zeros(2**num_active, dtype="float32")
    # print('merging with qubit states {}. {:d}-->{:d}'.format(
    #     qubit_states,
    #     len(unmerged_prob_vector),len(merged_prob_vector)))
    for active_qubit_states in itertools.product(["0", "1"], repeat=num_active):
        if len(active_qubit_states) > 0:
            merged_bin_id = int("".join(active_qubit_states), 2)
        else:
            merged_bin_id = 0
        for merged_qubit_states in itertools.product(["0", "1"], repeat=num_merged):
            active_ptr = 0
            merged_ptr = 0
            binary_state_id = ""
            for qubit_state in qubit_states:
                if qubit_state == "active":
                    binary_state_id += active_qubit_states[active_ptr]
                    active_ptr += 1
                elif qubit_state == "merged":
                    binary_state_id += merged_qubit_states[merged_ptr]
                    merged_ptr += 1
                else:
                    binary_state_id += "%s" % qubit_state
            state_id = int(binary_state_id, 2)
            merged_prob_vector[merged_bin_id] += unmerged_prob_vector[state_id]
    return merged_prob_vector
def merge_prob(data_folder, rank, num_workers):
    """
    The first merge of subcircuit probs using the target number of bins
    Saves the overhead of writing many states in the first SM recursion
    """

    meta_info = pickle.load(open("%s/meta_info.pckl" % (data_folder), "rb"))
    dd_schedule = pickle.load(open("%s/dd_schedule.pckl" % (data_folder), "rb"))

    merged_subcircuit_entry_probs = {}
    for subcircuit_idx in meta_info["entry_init_meas_ids"]:
        rank_jobs = find_process_jobs(
            jobs=list(meta_info["entry_init_meas_ids"][subcircuit_idx].keys()),
            rank=rank,
            num_workers=num_workers,
        )
        merged_subcircuit_entry_probs[subcircuit_idx] = {}
        for subcircuit_entry_init_meas in rank_jobs:
            subcircuit_entry_id = meta_info["entry_init_meas_ids"][subcircuit_idx][
                subcircuit_entry_init_meas
            ]
            unmerged_prob_vector = pickle.load(
                open(
                    "%s/subcircuit_%d_entry_%d.pckl"
                    % (data_folder, subcircuit_idx, subcircuit_entry_id),
                    "rb",
                )
            )
            merged_subcircuit_entry_probs[subcircuit_idx][
                subcircuit_entry_init_meas
            ] = merge_prob_vector(
                unmerged_prob_vector=unmerged_prob_vector,
                qubit_states=dd_schedule["subcircuit_state"][subcircuit_idx],
            )
    pickle.dump(
        merged_subcircuit_entry_probs,
        open("%s/rank_%d_merged_entries.pckl" % (data_folder, rank), "wb"),
    )
