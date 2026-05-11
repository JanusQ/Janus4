import rustworkx as rx
from qiskit.dagcircuit.dagnode import DAGNode, DAGOpNode, DAGInNode, DAGOutNode
from qiskit.dagcircuit import DAGCircuitError
from qiskit.converters import circuit_to_dag
from qiskit.circuit import QuantumCircuit, CircuitInstruction
from copy import deepcopy
from typing import Iterable,Union
from .blocknode import DAGBlockNode,SubDAGNode
from ..assessment import Metric
import os
from ..cutSolution import Solution
from .visualize import dag_drawer
class BasicCluster(object):
    def __init__(self,circuit: QuantumCircuit) -> None:
        self.dag = circuit_to_dag(circuit)
        self.circuit = circuit
        self.graph = self.dag._multi_graph
        self.width = circuit.width()
        self.cut_edges = []

    def group_node(self,dag,nodes:Iterable[Union[DAGBlockNode,DAGOpNode]]):
        new_node = DAGBlockNode(nodes,self.Metric)
        block_ids = [x._node_id for x in nodes]
        try:
            new_node._node_id = dag._multi_graph.contract_nodes(
            block_ids, new_node, check_cycle=True
        )
        except rx.DAGWouldCycle as ex:
            raise DAGCircuitError("Cycle in contruct") from ex
        dag._increment_op(new_node.op)
        for nd in nodes:
            dag._decrement_op(nd.op)
        return new_node
    
    def get_metric(self):
        for node in self._sim_dag.nodes():
            if isinstance(node,DAGOpNode):
                newnode = DAGBlockNode([node],self.Metric)
                self._sim_dag._multi_graph[node._node_id] = newnode
                self._sim_dag._increment_op(newnode.op)
                self._sim_dag._decrement_op(node.op)
                node = self._sim_dag._multi_graph[node._node_id]
                node.BlockToDag(self.dag)
                node.latency = node._latency()
                node.error = node._error()
            elif isinstance(node,DAGBlockNode):
                node.BlockToDag(self.dag)
                node.latency = node._latency()
                node.error =node._error()
    def get_subcircuits(self):
        self.subcircuits = []
        self.latency =[]
        self.error = []
        self.compute_graph = {}
        self.index_map = {}
        for index,node in enumerate(self._Block_dag.nodes()):
            if isinstance(node,SubDAGNode):
                node.BlockToDag()
                node.latency = node._latency()
                node.error =node._error()
                self.subcircuits.append(node.circuit)
                self.latency.append(node.latency)
                self.error.append(node.error)
                node.op.name = "SubCircuit"+str(index-2*self.width)
                self.index_map[node._node_id] = index-2*self.width
            elif isinstance(node,DAGBlockNode) or isinstance(node,DAGOpNode):
                subdag = SubDAGNode(node,self.dag,self.Metric)
                subdag._node_id = node._node_id
                self._Block_dag._multi_graph[node._node_id] = subdag
                subdag.latency = subdag._latency()
                subdag.error = subdag._error()
                self.subcircuits.append(subdag.circuit)
                self.latency.append(subdag.latency)
                self.error.append(subdag.error)
                subdag.op.name = "SubCircuit"+str(index-2*self.width)
                self.index_map[subdag._node_id] = index-2*self.width
        self.cut_num = -self._Block_dag.width()
        for circuit_qubit in self._Block_dag.qubits:
            self.compute_graph[circuit_qubit] = []
            for node in self._Block_dag.nodes_on_wire(wire=circuit_qubit, only_ops=False):
                if isinstance(node,SubDAGNode):
                    self.cut_num+=1
                    path_element = {
                        "subcircuit_idx": self.index_map[node._node_id],
                        "subcircuit_qubit": circuit_qubit,
                    }
                    self.compute_graph[circuit_qubit].append(path_element)
    def get_block(self,dag):
        name = dag.name or None
        circuit = QuantumCircuit(
            dag.qubits,
            dag.clbits,
            *dag.qregs.values(),
            *dag.cregs.values(),
            name=name,
            global_phase=dag.global_phase,
        )
        circuit.metadata = dag.metadata
        circuit.calibrations = dag.calibrations

        for node in dag.topological_nodes():
            if isinstance(node,SubDAGNode):
                circuit._append(CircuitInstruction(deepcopy(node.op), node.qargs, node.cargs))

        circuit.duration = dag.duration
        circuit.unit = dag.unit
        return circuit
    
    def draw_solution(self,id):
        os.makedirs( f'result/{id}/',exist_ok=True)
        self.circuit.draw(output='mpl',filename= f'result/{id}/origin.png')
        self.Block_circuit.draw(output='mpl',filename= f'result/{id}/clustered.png')
        dag_drawer(self._Block_dag)
        for i,subcirc in enumerate(self.subcircuits):
            subcirc.draw(output='mpl',filename= f'result/{id}/subcircuit{i}.png')
    def find_combine_num(self,numbers:Iterable[Union[int,float]],max_sum:Union[int,float])->Iterable[Union[int,float]]:
        """find the groups of numbers which satisfies the sum of every group < max_sum 

        Args:
            numbers (Iterable[Union[int,float]]): the list of numbers
            max_sum (Union[int,float]): the required max sum
        Returns:
            Iterable[Union[int,float]]: the list of groups
        """                
        def iter_find(msum):
            required= []
            others = [n for n in numbers if n <= msum]
            if others:
                max_next = max(others)
                numbers.remove(max_next)
                required.append(max_next)
                required+=iter_find(msum- max_next)
            return required
        res = []
        numbers.sort(reverse=True)
        numbers_copy = deepcopy(numbers)
        for num in numbers_copy:
            if num not in numbers:
                continue
            numbers.remove(num)
            res.append([num]+iter_find(max_sum - num))
        return res

    def merge_subcircuits_num(self):
        merged_nums=[]
        for index,node in enumerate(self._Block_dag.nodes()):
            if isinstance(node,SubDAGNode):
                node.BlockToDag()
                node.latency = node._latency()
                node.error =node._error()
                merged_nums.append(len(node.qargs))
        return len(self.find_combine_num(merged_nums,self.QPU_width))
    
    def get_basic_solution(self,qpu):
        self.QPU_width = qpu.width
        self.Metric = qpu
        self.cluster()
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
        # self.draw_solution(1)
        return Solution('basic_cluster',self.solution)
    
    def _simplify(self):
        ### copy 算法有问题 node——id 为 -1
        self._sim_dag= self.resetIndex(deepcopy(self.dag))
        for node in  self._sim_dag.topological_op_nodes():
            predecessors = list(self._sim_dag.predecessors(node))
            Groups = []
            if len(predecessors)==1 and not isinstance(predecessors[0],DAGInNode):
                Groups.append(predecessors[0])
            else:
                for pre_node in predecessors:
                    if not isinstance(pre_node,DAGInNode) and len(pre_node.qargs) ==1:
                        Groups.append(pre_node)
            if Groups:
                self.group_node(self._sim_dag,[node,*Groups])
        self.get_metric()
    def resetIndex(self,dag):
        for node_id in dag._multi_graph.node_indexes():
            dag._multi_graph[node_id]._node_id = node_id
        return dag
    def cluster(self):
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
                self._iter_layer(layer)

    def _init_layer(self,front):
        for node in front:
            if isinstance(node, DAGOutNode):
                continue
            subdag = SubDAGNode(node,self.dag,self.Metric)
            subdag._node_id = node._node_id
            self._Block_dag._multi_graph[node._node_id]= subdag
            self._Block_dag._increment_op(subdag.op)
            self._Block_dag._decrement_op(node.op)



    def Group_check(self,dag,nodes:Iterable[Union[DAGOpNode,DAGBlockNode,SubDAGNode]]):
        ### need rewrite
        block_qargs = set()
        for node in nodes:
            block_qargs |= set(node.qargs)
        dag = self.resetIndex(deepcopy(dag))
        new_node = "test"
        try:
            dag._multi_graph.contract_nodes(
            [x._node_id for x in nodes], new_node, check_cycle=True
        )
        except rx.DAGWouldCycle as ex:
            return False
        return len(block_qargs)<= self.QPU_width
    
    def expand_subdag(self,subdagnode:SubDAGNode,node:Union[DAGBlockNode,DAGOpNode]):
        origin_op = subdagnode.op
        node_ids =[subdagnode._node_id,node._node_id]
        subdagnode.append(node)
        try:
            subdagnode._node_id = self._Block_dag._multi_graph.contract_nodes(
            node_ids, subdagnode, check_cycle=True
        )
        except rx.DAGWouldCycle as ex:
            raise DAGCircuitError("Cycle in construct") from ex
        
        self._Block_dag._increment_op(subdagnode.op)
        self._Block_dag._decrement_op(origin_op)
        self._Block_dag._decrement_op(node.op)
        return subdagnode._node_id
    
    def Group_nodes(self,subdagnodes:Iterable[SubDAGNode],block_node:Union[DAGBlockNode,DAGOpNode]):
        if len(subdagnodes) ==1:
            return self.expand_subdag(subdagnodes[0],block_node)
        self._Block_dag._decrement_op(subdagnodes[0].op)
        block_ids = [x._node_id for x in [*subdagnodes,block_node]]
        new_node = subdagnodes[0].group(subdagnodes[1],block_node)

        try:
            new_node._node_id = self._Block_dag._multi_graph.contract_nodes(
            block_ids, new_node, check_cycle=True
        )
        except rx.DAGWouldCycle as ex:
            raise DAGCircuitError("Cycle in construct") from ex
        
        self._Block_dag._increment_op(new_node.op)

        for nd in [subdagnodes[1],block_node]:
            self._Block_dag._decrement_op(nd.op)
        
        return new_node._node_id

    def _iter_layer(self,layer):
        # print(layer)
        for node in layer:
            if isinstance(node,DAGOutNode):
                continue
            elif isinstance(node,SubDAGNode):
                raise ValueError("something wrong with iter")
            latency = {}
            error = {}
            ### 遍历每个节点的父节点，也就是子图
            wire_map = {}
            parents = []
            for parent_id,_,q in self._Block_dag._multi_graph.in_edges(node._node_id):
                parent_node = self._Block_dag._multi_graph[parent_id]
                if not isinstance(parent_node,DAGInNode):
                    wire_map[parent_node]= q
                    parents.append(parent_node)
            parents = list(set(parents))
            if self.Group_check(self._Block_dag,[*parents,node]):
                self.Group_nodes(parents,node)
            else:
                parent_node_q={}
                parent_nodes =[]
                for parent_node in parents:
                    q = wire_map[parent_node]
                    parent_node_q[q] = parent_node
                    if self.Group_check(self._Block_dag,[parent_node,node]):
                        latency[q] = parent_node.latency[q]+node.latency[q]
                        error[q] = parent_node.error[q]+node.error[q]
                        parent_nodes.append(parent_node)
                if not parent_nodes:
                    self._init_layer([node])
                elif len(parent_nodes)==2:
                    self.expand_subdag(parent_node_q[node.qargs[1]],node)
                    parent_node_q[node.qargs[0]].kill(node.qargs[0])
                else:
                    self.expand_subdag(parent_nodes[0],node)
                


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
