def QpuList2allocation(qpu_list):
    allocation = [0]*sum([len(qpu) for qpu in qpu_list])
    for qpu_idx,qpu in enumerate(qpu_list):
        for q in qpu:
            allocation[q] = qpu_idx
    return allocation