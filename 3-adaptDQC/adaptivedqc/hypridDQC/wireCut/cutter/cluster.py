
from qiskit.dagcircuit.dagnode import DAGInNode, DAGOutNode
from qiskit.circuit import QuantumCircuit
from copy import deepcopy
from .blocknode import SubDAGNode
from ..assessment import QPU
from ..cutSolution import Solution
from .basicCluster import BasicCluster
from typing import Iterable
class Cluster(BasicCluster):
    def __init__(self,circuit: QuantumCircuit) -> None:
        super().__init__(circuit)

    def _metric_value(self, metric_dict, qubit, default=0):
        if qubit in metric_dict:
            return metric_dict[qubit]
        if metric_dict:
            return max(metric_dict.values())
        return default
        
    def Latency_Cluster(self):
        self._simplify()
        basic_solution = self.get_basic_solution(self.Metric)
        self.max_latency = min(max(item.values()) for item in basic_solution.latency)
        self._Block_dag= self.resetIndex(deepcopy(self._sim_dag))
        layer_index = 0
        layers = self._Block_dag.multigraph_layers()
        next(layers)
        for layer in layers:
            print("------------{}-layer--------------".format(layer_index))
            layer_index += 1
            if layer_index == 1:
                self._init_layer(layer)
            else:
                self._iter_layer_latency(layer)
    def _iter_layer_latency(self,layer:Iterable):
        # print(layer)
        for node in layer:
            if isinstance(node, DAGOutNode):
                continue
            elif isinstance(node, SubDAGNode):
                raise ValueError("something wrong with iter")
            latency = {}
            ### 遍历每个节点的父节点，也就是子图
            wire_map = {}
            parents = []
            for parent_id, _, q in self._Block_dag._multi_graph.in_edges(node._node_id):
                parent_node = self._Block_dag._multi_graph[parent_id]
                if not isinstance(parent_node, DAGInNode):
                    wire_map[parent_node] = q
                    parents.append(parent_node)
            parents = list(set(parents))
            for parent_node in parents:
                q = wire_map[parent_node]
                latency[q] = self._metric_value(parent_node.latency, q)+self._metric_value(node.latency, q)
                if latency[q] > self.max_latency:
                    parent_node.kill(q)
                    parents.remove(parent_node)
                    if parent_node.isended():
                        if parent_node.latency_all < self.max_latency:
                            self.max_latency = parent_node.latency_all
            if not parents:
                continue
            if self.Group_check(self._Block_dag, [*parents, node]):
                self.Group_nodes(parents, node)
            else:
                parent_node_q = {}
                parent_nodes = []
                for parent_node in parents:
                    q = wire_map[parent_node]
                    parent_node_q[q] = parent_node
                    latency[q] = self._metric_value(parent_node.latency, q)+self._metric_value(node.latency, q)
                    if self.Group_check(self._Block_dag, [parent_node, node]):
                        parent_nodes.append(parent_node)
                    else:
                        parent_node.kill(q)
                        if parent_node.isended():
                            if parent_node.latency_all < self.max_latency:
                                self.max_latency = parent_node.latency_all
                if not parent_nodes:
                    self._init_layer([node])
                elif len(parent_nodes) == 2:
                    if latency[node.qargs[0]] > latency[node.qargs[1]]:
                        self.expand_subdag(parent_node_q[node.qargs[1]], node)
                        parent_node_q[node.qargs[0]].kill(node.qargs[0])
                # self._Block_dag._multi_graph.remove((parent_q_node[node.qargs[0]],node))
                    else:
                        self.expand_subdag(parent_node_q[node.qargs[0]], node)
                        parent_node_q[node.qargs[1]].kill(node.qargs[1])
                else:
                    self.expand_subdag(parent_nodes[0], node)
    def Error_Cluster(self):
        self._simplify()
        self._Block_dag= self.resetIndex(deepcopy(self._sim_dag))
        layer_index = 0
        layers = self._Block_dag.multigraph_layers()
        next(layers)
        for layer in layers:
            print("------------{}-layer--------------".format(layer_index))
            layer_index += 1
            if layer_index == 1:
                self._init_layer(layer)
            else:
                self._iter_error_latency(layer)
    def _iter_error_latency(self,layer):
        for node in layer:
            if isinstance(node, DAGOutNode):
                continue
            elif isinstance(node, SubDAGNode):
                raise ValueError("something wrong with iter")
            error = {}
            ### 遍历每个节点的父节点，也就是子图
            wire_map = {}
            parents = []
            for parent_id, _, q in self._Block_dag._multi_graph.in_edges(node._node_id):
                parent_node = self._Block_dag._multi_graph[parent_id]
                if not isinstance(parent_node, DAGInNode):
                    wire_map[parent_node] = q
                    parents.append(parent_node)
            parents = list(set(parents))
            for parent_node in parents:
                q = wire_map[parent_node]
                error[q] = self._metric_value(parent_node.error, q)+self._metric_value(node.error, q)
            if not parents:
                continue
            if self.Group_check(self._Block_dag, [*parents, node]):
                self.Group_nodes(parents, node)
            else:
                parent_node_q = {}
                parent_nodes = []
                for parent_node in parents:
                    q = wire_map[parent_node]
                    parent_node_q[q] = parent_node
                    error[q] = self._metric_value(parent_node.error, q)+self._metric_value(node.error, q)
                    if self.Group_check(self._Block_dag, [parent_node, node]):
                        parent_nodes.append(parent_node)
                    else:
                        parent_node.kill(q)
                if not parent_nodes:
                    self._init_layer([node])
                elif len(parent_nodes) == 2:
                    if error[node.qargs[0]] > error[node.qargs[1]]:
                        self.expand_subdag(parent_node_q[node.qargs[1]], node)
                        parent_node_q[node.qargs[0]].kill(node.qargs[0])
                # self._Block_dag._multi_graph.remove((parent_q_node[node.qargs[0]],node))
                    else:
                        self.expand_subdag(parent_node_q[node.qargs[0]], node)
                        parent_node_q[node.qargs[1]].kill(node.qargs[1])
                else:
                    self.expand_subdag(parent_nodes[0], node)
        
    def get_solution(self,qpu:QPU,opt_type:str='latency'):
        self.QPU_width = qpu.width
        self.Metric = qpu
        if opt_type == 'latency':
            self.Latency_Cluster()
        elif opt_type == 'error':
            self.Error_Cluster()
        else:
            raise ValueError("opt_type must be 'latency' or 'error'")
        self.get_subcircuits()
        self.Block_circuit = self.get_block(self._Block_dag)
        counter = get_counter(self.subcircuits,self.compute_graph)
        self.solution = {
                "subcircuits": self.subcircuits,
                "complete_path_map": self.compute_graph,
                "num_cuts": self.cut_num,
                "counter": counter,
                "subcircuits_num": self.merge_subcircuits_num(),
                "latency":self.latency,
                "error":self.error
            }
        return Solution('basic_cluster',self.solution)     


def get_pairs(complete_path_map):
    O_rho_pairs = []
    for input_qubit in complete_path_map:
        path = complete_path_map[input_qubit]
        if len(path) > 1:
            for path_ctr, item in enumerate(path[:-1]):
                O_qubit_tuple = item
                rho_qubit_tuple = path[path_ctr + 1]
                O_rho_pairs.append((O_qubit_tuple, rho_qubit_tuple))
    return O_rho_pairs


def get_counter(subcircuits,complete_path_map):
    counter = {}
    for subcircuit_idx, subcircuit in enumerate(subcircuits):
        counter[subcircuit_idx] = {
            "effective": subcircuit.num_qubits,
            "rho": 0,
            "O": 0,
            "d": subcircuit.num_qubits,
            "depth": subcircuit.depth(),
            "size": subcircuit.size(),
        }
    for pair in get_pairs(complete_path_map):
        O_qubit, rho_qubit = pair
        counter[O_qubit["subcircuit_idx"]]["effective"] -= 1
        counter[O_qubit["subcircuit_idx"]]["O"] += 1
        counter[rho_qubit["subcircuit_idx"]]["rho"] += 1
    return counter
