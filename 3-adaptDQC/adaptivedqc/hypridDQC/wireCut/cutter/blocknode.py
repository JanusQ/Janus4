from qiskit.dagcircuit.dagnode import DAGNode, DAGOpNode
from qiskit.dagcircuit import DAGCircuit
from qiskit.dagcircuit.exceptions import DAGCircuitError
from qiskit.converters import dag_to_circuit
from qiskit.circuit import Instruction
from typing import Iterable,Union

from ..assessment import Metric

class DAGBlockNode(DAGNode):

    """Object to represent an BLOCK represent the node in the DAGCircuit."""
    ### 及时更新属性
    # __slots__ = ["op", "qargs", "cargs", "sort_key","dag","latency","circuit","fidelity","block_nodes","dagcircuit"]

    def __init__(self,nodes:Iterable[DAGOpNode],metric:Metric):
        """Create an Instruction node"""
        
        super().__init__()
        block_qargs = set()
        block_cargs = set()
        block_node_ids = []
        if not nodes:
            raise DAGCircuitError("Can't replace an empty node_block")
       
        for node in nodes:
            block_qargs |= set(node.qargs)
            if isinstance(node,DAGOpNode):
                block_node_ids.append(node._node_id)
                if getattr(node.op, "condition", None):
                    block_cargs |= set(node.cargs)
            else:
                block_node_ids+=node.block_nodes
        self.op = Instruction(name="BLOCK"+str(len(block_node_ids)),num_qubits=len(block_qargs),num_clbits=len(block_cargs),params=[])
        self.block_nodes = block_node_ids
        self.qargs = sorted(block_qargs, key=lambda x: x.index)
        self.cargs = sorted(block_cargs, key=lambda x: x.index)
        self.metric = metric
        self.qargs_kill = []

    @property
    def name(self):
        """Returns the Instruction name corresponding to the op for this node"""
        return self.op.name

    @name.setter
    def name(self, new_name):
        """Sets the Instruction name corresponding to the op for this node"""
        self.op.name = new_name

    def __repr__(self):
        """Returns a representation of the DAGOpNode"""
        return f"DAGBLockNode(op={self.op}, qargs={self.qargs}, cargs={self.cargs},nodes={self.block_nodes})"
    def BlockToDag(self,origin_dag):
        dag = DAGCircuit()
        dag.add_qubits(self.qargs)
        dag.add_clbits(self.cargs)
        for node_id in sorted(self.block_nodes):
            node = origin_dag.node(node_id)
            dag.apply_operation_back(node.op.copy(), node.qargs, node.cargs)
        self.dagcircuit = dag
        return dag
    @property
    def circuit(self):
        return dag_to_circuit(self.dagcircuit)
    def _latency(self):
        latency_dict = {}
        for q in self.qargs:
            latency_dict[q] = 0
        for gate in self.dagcircuit.topological_op_nodes():
            q_indexes = [q._index for q in gate.qargs]
            max_latency = max([latency_dict[q] for q in gate.qargs])+self.metric.latency(gate.op.name,q_indexes)
            for q in gate.qargs:
                latency_dict[q] = max_latency
            
        return latency_dict
    def _error(self):
        error_dict = {}
        for q in self.qargs:
            error_dict[q] = 0
        for gate in self.dagcircuit.topological_op_nodes():
            q_indexes = [q._index for q in gate.qargs]
            error = self.metric.gate_error(gate.op.name,q_indexes)
            for q in gate.qargs:
                error_dict[q]+= error
        return error_dict


    @property
    def latency_all(self):
        return max(self.latency.values())
    @property
    def fidelity(self):
        fidelity_dict ={}
        for k,v in self.error.items():
            fidelity_dict[k] =  1-v
        return fidelity_dict

    def kill(self,q):
        self.qargs_kill.append(q)

    def isended(self):
        return len(self.qargs_kill)==len(self.qargs)

    
    
class SubDAGNode(DAGBlockNode):
    def __init__(self,node:DAGBlockNode,parent_dag:DAGCircuit,metric:Metric):
        if isinstance(node,DAGOpNode):
            super().__init__([node],metric)
        else:
            self.op = Instruction(name="SubCircuit"+str(len(node.block_nodes)),num_qubits=len(node.qargs),num_clbits=len(node.cargs),params=[])
            self.qargs = node.qargs
            self.cargs = node.cargs
            self.block_nodes = node.block_nodes
            self.latency = node.latency
            self.error  = node.error
            self.metric = metric
        self.qargs_kill = []
        self.parent_dag = parent_dag
        self.dagcircuit = self.BlockToDag()
        self.sort_key = str(self.qargs)


    def append(self,node:Union[DAGBlockNode,DAGOpNode]):
        block_cargs = set(self.cargs)
        node_ids = []
        if isinstance(node,DAGOpNode):
            node_ids.append(node._node_id)
            if getattr(node.op, "condition", None):
                block_cargs |= set(node.cargs)
        else:
            node_ids+=node.block_nodes
        # wire_pos_map = {q:i for i,q in enumerate(block_qargs)}
        self.block_nodes += node_ids
        for q in set(node.qargs).difference(set(self.qargs)):
            self.error[q] =0
            self.latency[q] = 0
        ## append is apply after subdag
        res_lat ={q:0 for q in node.qargs}
        for gate_id in node_ids:
            gate = self.parent_dag.node(gate_id)
            if len(gate.qargs) ==1:
                q_indexes = [q._index for q in gate.qargs]
                res_lat[gate.qargs[0]]+= self.metric.latency(gate.op.name,q_indexes)
            else:
                break
        
        for q in node.qargs:
            if q not in self.qargs:
                self.latency[q] =0
                self.qargs.append(q)
                self.error[q]= node.error[q]
            else:
                self.error[q]+= node.error[q]
        for q in node.qargs:
            self.latency[q] += res_lat[q]
        max_latency = max(self.latency[q] for q in node.qargs)
        for q in node.qargs:
            self.latency[q] = max_latency+node.latency[q]-res_lat[q]
        
        self.qargs=sorted(self.qargs, key=lambda x: x.index)
        self.cargs=sorted(block_cargs, key=lambda x: x.index)
        newOp = Instruction(name="SubCircuit"+str(len(self.block_nodes)),num_qubits=len(self.qargs),num_clbits=len(self.cargs),params=[])         
        # Create replacement node
        self.op = newOp
        self.sort_key = str(self.qargs)


    def group(self,subdagnode,node=None):
        block_qargs = set(self.qargs) | set(subdagnode.qargs)
        block_cargs = set(self.cargs) | set(subdagnode.cargs)
        node_ids = []
        if isinstance(node,DAGOpNode):
            node_ids.append(node._node_id)
            if getattr(node.op, "condition", None):
                block_cargs |= set(node.cargs)
        else:
            node_ids+=node.block_nodes
        self.block_nodes +=subdagnode.block_nodes
        self.block_nodes += node_ids
        self.error.update(subdagnode.error)
        self.latency.update(subdagnode.latency)
        ## append is apply after subdag
        res_lat ={q:0 for q in node.qargs}
        for gate_id in node_ids:
            gate = self.parent_dag.node(gate_id)
            if len(gate.qargs) ==1:
                q = gate.qargs[0]
                res_lat[q]+= self.metric.latency(gate.op.name,[q.index])
            else:
                break
        for q in node.qargs:
            self.error[q]+= node.error[q]
            self.latency[q] += res_lat[q]
        max_latency = max(self.latency[q] for q in node.qargs)
        for q in node.qargs:
            self.latency[q] = max_latency+node.latency[q]-res_lat[q]
        
        self.qargs=sorted(block_qargs, key=lambda x: x.index)
        self.cargs=sorted(block_cargs, key=lambda x: x.index)
        newOp = Instruction(name="SubCircuit"+str(len(self.block_nodes)),num_qubits=len(block_qargs),num_clbits=len(block_cargs),params=[])         
        # Create replacement node
        self.op = newOp
        self.sort_key = str(self.qargs)
        return self
    
    def kill(self,q):
        self.qargs_kill.append(q)
    def isended(self):
        return len(self.qargs_kill)==len(self.qargs) 
    def BlockToDag(self):
        dag = DAGCircuit()
        dag.add_qubits(self.qargs)
        dag.add_clbits(self.cargs)
        for node_id in sorted(self.block_nodes):
            node = self.parent_dag.node(node_id)
            dag.apply_operation_back(node.op.copy(), node.qargs, node.cargs)
        self.dagcircuit = dag
        return dag
