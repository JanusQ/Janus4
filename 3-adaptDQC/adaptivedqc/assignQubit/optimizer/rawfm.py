import warnings
import random
from functools import reduce
from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag
from ..util import QpuList2allocation

def transform_to_hyper(circuit: QuantumCircuit):
    """
    负责将电路转换为超图，此类适合作为静态方法放入原类中
    """
    warnings.filterwarnings('ignore')
    vertexes = list(range(circuit.num_qubits))
    edges = []
    for gate in circuit.data:
        if gate.operation.name == 'cx':
            gate_qubits = gate.qubits
            edge = [gate_qubits[0].index, gate_qubits[1].index]
            edges.append(edge)
        else:
            edges.append([gate.qubits[0].index])
    return vertexes, edges


def hyper(circuit: QuantumCircuit):
    """
    论文中的转换超图方式
    """
    V = set()
    H = set()
    dag = circuit_to_dag(circuit)
    for wire in dag.wires:
        V = V | {wire}
        hedge = {wire}
        for gate in dag.nodes_on_wire(wire, only_ops=True):
            if gate.name == 'cx':
                V = V | {(gate.name, gate.qargs, gate)}
                hedge = hedge | {(gate.name, gate.qargs, gate)}
            else:
                H = H | {tuple(hedge)}
                hedge = {wire}
        H = H | {tuple(hedge)}
    v_map = {}
    v_map_reverse = {}
    for node_id, v in enumerate(V):
        v_map[node_id] = v
        v_map_reverse[v] = node_id
    new_V = list(range(len(V)))
    new_H = []
    for h in H:
        hedge = []
        for v in h:
            hedge.append(v_map_reverse[v])
        new_H.append(hedge)
    return new_V, new_H, v_map

def get_max_gain_v(left, right, unmoved_v, edges):
    """
    论文中的目标函数，仅仅以cutsize最小作为目标函数
    """

    def fs(x):
        # 求fs
        fs = 0
        for hedge in edges:
            if x in hedge:
                if (x in left and all([i in right for i in hedge if i != x])) or (
                        x in right and all([i in left for i in hedge if i != x])):
                    fs += 1
        return fs

    def te(x):
        # 求te
        te = 0
        for hedge in edges:
            if x in hedge:
                if all([i in left for i in hedge]) or all([i in right for i in hedge]):
                    te += 1
        return te

    gain = {}
    # 求gain
    for i in unmoved_v:
        gain[i] = fs(i) - te(i)
    # 获取最大gain且不违反约束的点
    sorted_unmoved = sorted(gain, key=lambda k: gain[k], reverse=True)
    for i in sorted_unmoved:
        if (i in right and len(left) - len(right) < 1) or (i in left and len(right) - len(left) < 1):
            return i, gain[i]


def fiduccia_mattheyses(graph):
    """
    fm算法
    """
    vertexes, edges = graph[0], graph[1]
    # 初始化边集
    num_v = len(vertexes)
    random.shuffle(vertexes)
    num_left = int(num_v // 2)
    left = vertexes[:num_left]
    right = vertexes[num_left:]
    # 移动所有没有移动的点
    unmoved_v = vertexes.copy()
    # 存储所有结果
    history = []
    gain_sum = 0
    while unmoved_v:
        current_v, gain = get_max_gain_v(
            left, right, unmoved_v, edges)
        unmoved_v.remove(current_v)
        gain_sum += gain
        # 移动点集
        if current_v in left:
            left.remove(current_v)
            right.append(current_v)
        else:
            left.append(current_v)
            right.remove(current_v)
        # 记录
        history.append({
            'left': left.copy(),
            'right': right.copy(),
            'move_v': current_v,
            'gain': gain,
            'gain_sum': gain_sum
        })
    return reduce(lambda x, y: x if x['gain_sum'] > y['gain_sum'] else y, history)


def k_fiduccia_mattheyses(circuit, md):
    """
    将电路切分成小于等于md的子电路，返回每个子电路的qubit
    """
    graph = transform_to_hyper(circuit)

    result = []

    def k_f(graph, md=4):
        num_qubits = len(graph[0])
        if num_qubits <= md:
            result.append(graph[0])
            return
        res = fiduccia_mattheyses(graph)
        left = res['left']
        right = res['right']
        edges = graph[1]
        k_f((left, edges), md=md)
        k_f((right, edges), md=md)

    k_f(graph, md=md)
    return result


def RawFM(circuit, md):
    qubit_list = k_fiduccia_mattheyses(
        circuit, md)
    allocation = QpuList2allocation(qubit_list)
    return allocation

