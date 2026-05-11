from qiskit.circuit import Gate,CircuitInstruction,QuantumCircuit
from qiskit.extensions import XGate,SXGate,RZGate
from qiskit.circuit import Qubit
from typing import Iterable
import numpy as np
from qiskit.circuit import CircuitInstruction
from itertools import combinations
from copy import deepcopy
from functools import reduce
from qiskit import QuantumRegister,ClassicalRegister
from qiskit.compiler import transpile
def flatten_list(nested_list):
    flat_list = []
    for item in nested_list:
        if isinstance(item, list):
            flat_list.extend(flatten_list(item))
        else:
            flat_list.append(item)
    return flat_list

class EPRGate:
    """
    epr类,加epr门时用
    """

    def __init__(self, type:int,teleq:int, qubits:Iterable[Qubit], frontOrBack:int):
        """EPRgate build 

        Args:
            type (str): 0 'telegate' or 1 'teledata
            teleq (Qubit): the qubit to transport index
            qubits (Iterable[Qubit]): the qubit of all trans
            frontOrBack (int): the front 0  or back 1 epr
        """
        self.type = type
        if self.type == 'telegate':
            self.value = 1/2
        elif self.type == 'teledata':
            self.value = 1
        else:
            raise ValueError("the type of epr is only 'telegate' or 'teledata'")
        
        self.teleq = teleq
        self.qubits = qubits
        self.frontOrBack = frontOrBack
        self.label = 'f' if self.frontOrBack == 0 else 'b'
        self.name = 'epr'

    def get_gate(self):
        """get the epr gate as a circuit instruction
        """
        gate = CircuitInstruction(Gate('epr', len(self.qubits),[],label=self.label), qubits=self.qubits)
        gate.operation.value = self.value
        gate.operation.teleq = self.teleq
        return gate

class Partcompile:
    """
    分布式编译类
    """
    def __init__(self,circuit:QuantumCircuit,allocation:list,compile:bool=False) -> None:
        """

        Args:
            circuit (QuantumCircuit): circuit to compile

            allocation (list): the allocation of qubits, the format is [0,0,1,1,2,2,3,3,4,4], the number is the index of qpu
            here, the qubits of circuit is [0,1,2,3,4,5,6,7,8,9], allocation [0,0,1,1,2,2,3,3,4,4] means the qubit 0,1 is in qpu 0, qubit 2,3 is in qpu 1, qubit 4,5 is in qpu 2, qubit 6,7 is in qpu 3, qubit 8,9 is in qpu 4

            compile (bool, optional): if the circuit has not been compiled to the basic gate,please set it False. Defaults to False.
        """
        if compile:
            ## 如果没有编译过，就编译到对应的芯片上
            self.circuit = self.compileToBackend(circuit)
        else:
            self.circuit = circuit
        self.allocation = allocation
        self.qpumax = max(allocation)+1
        self.gate_set = deepcopy(self.circuit.data)
        self.gate_ids = list(range(len(self.gate_set)))
        self.gate_max_id = len(self.gate_set)-1
        self.epr_reg_num = 0
    def get_epr_circuit(self):
        """获得分布式编译需要的EPR 数目,以及插入epr对的位置电路

        Returns:
            (EPRNum,EPR_circuit): EPR 数目,插入epr对的位置电路
        """
        self.get_continue_group()
        self.insert_epr()
        self.get_compile_circuit()
        epr_num = self.get_epr_num()
        return epr_num,self.epr_circuit
    
    def run(self):
        """
        获得分布式编译电路，在模拟器上可以直接执行
        """
        self.get_continue_group()
        self.insert_epr()
        self.get_compile_circuit()
        return self.compile_with_teleportion()
    def get_h_gate(self,wire:Qubit):
        """get the h gate  as id,x,sx,rz,cx basis
        """
        cir = QuantumCircuit(1)
        cir.h(0)
        qc_transpiled = transpile(cir, basis_gates=['id','x','sx','rz','cx'],optimization_level=3)
        h_index = []
        for i in range(len(qc_transpiled.data)):
            qc_transpiled.data[i].qubits = (wire,)
            self.gate_set.append(qc_transpiled.data[i])
            self.gate_max_id += 1
            h_index.append(self.gate_max_id)
        return h_index
    
    def get_remote_gates(self) -> None:
        """get the remote gates,the remote gate is the gate that the qubits are not in the same qpu
        """
        self.remote_gates = [[[] for i in range(self.qpumax)  if i < j] for j in range(self.qpumax)]
        for node_id in self.gate_ids:
            if self.gate_set[node_id].operation.num_qubits==2 and self.allocation[self.gate_set[node_id].qubits[0].index] != self.allocation[self.gate_set[node_id].qubits[1].index]:
                alls = sorted([self.allocation[self.gate_set[node_id].qubits[0].index],self.allocation[self.gate_set[node_id].qubits[1].index]])
                self.remote_gates[alls[1]][alls[0]].append(node_id)
    
    def get_nodes(self,j,i)->list:
        """get all sequential gates that contains all  remote gates in the jth qpu and ith qpu
        """
        if not self.remote_gates[j][i]:
            return  []
        nodes = []
        for node_id in self.gate_ids:
            if self.remote_gates[j][i][0] <= node_id  <= self.remote_gates[j][i][-1]:
                nodes.append(node_id)
        return nodes
    
    def get_continue_group(self):
        """get the continue group of gates, a continue group means the gates that has one qubit in same,and the gates are commutative,which means the gates can be executed in any order
        """
        self.get_remote_gates()
        self.remote_group = {}
        self.remote_map = {}
        self.qtele_map = {}
        for idx,jdx in combinations(range(self.qpumax),2):
            # print(jdx,idx )
            nodes = self.get_nodes(jdx,idx)
            def iter_continue0(i,qdx):
                if i+1 >= len(nodes):
                    return []
                if nodes[i+1] in flatten_list(continue_remote_gates):
                    if self.gate_set[nodes[i+1]].qubits[0].index == qdx:
                        return []
                    else:
                        return iter_continue0(i+1,qdx)
                    
                if self.gate_set[nodes[i+1]].qubits[0].index == qdx:
                    if self.gate_set[nodes[i+1]].operation.name == 'sx':
                        return []
                    else:
                        return [nodes[i+1]]+ iter_continue0(i+1,qdx)
                else:
                    if self.gate_set[nodes[i+1]].operation.name != 'cx':
                        return iter_continue0(i+1,qdx)
                    else:
                        if self.gate_set[nodes[i+1]].qubits[1].index == qdx:
                            return []
                        else:
                            return iter_continue0(i+1,qdx)
            
            def iter_continue1(i,qdx):
                if i+1 >= len(nodes):
                    return []
                if nodes[i+1] in flatten_list(continue_remote_gates):
                    if self.gate_set[nodes[i+1]].qubits[1].index == qdx:
                        return []
                    else:
                        return iter_continue1(i+1,qdx)
                if self.gate_set[nodes[i+1]].operation.name != 'cx':
                    if self.gate_set[nodes[i+1]].qubits[0].index == qdx:
                        if self.gate_set[nodes[i+1]].operation.name == 'rz':
                            return []
                        else:
                            return [nodes[i+1]]+ iter_continue1(i+1,qdx)
                    else:
                        return iter_continue1(i+1,qdx)
                else:
                    if self.gate_set[nodes[i+1]].qubits[1].index == qdx:
                        return [nodes[i+1]]+ iter_continue1(i+1,qdx)
                    elif self.gate_set[nodes[i+1]].qubits[0].index == qdx:
                        return []
                    else:
                        return iter_continue1(i+1,qdx)
            
            def get_front0(i,qdx):
                if i == 0:
                    return []
                if nodes[i-1] in flatten_list(continue_group):
                    return []
                if self.gate_set[nodes[i-1]].qubits[0].index == qdx:
                    if self.gate_set[nodes[i-1]].operation.name == 'sx':
                        return []
                    else:
                        return [nodes[i-1]]+ get_front0(i-1,qdx)
                else:
                    if self.gate_set[nodes[i-1]].operation.name != 'cx':
                        return get_front0(i-1,qdx)
                    else:
                        if self.gate_set[nodes[i-1]].qubits[1].index == qdx:
                            return []
                        else:
                            return get_front0(i-1,qdx)
            def get_front1(i,qdx):
                if i == 0:
                    return []
                if nodes[i-1] in flatten_list(continue_group):
                    return []
                if self.gate_set[nodes[i-1]].operation.name != 'cx':
                    if self.gate_set[nodes[i-1]].qubits[0].index == qdx:
                        if self.gate_set[nodes[i-1]].operation.name == 'rz':
                            return []
                        else:
                            return [nodes[i-1]]+ get_front1(i-1,qdx)
                    else:
                        return get_front1(i-1,qdx)
                else:
                    if self.gate_set[nodes[i-1]].qubits[1].index == qdx:
                        return [nodes[i-1]]+ get_front1(i-1,qdx)
                    elif self.gate_set[nodes[i-1]].qubits[0].index == qdx:
                        return []
                    else:
                        return get_front1(i-1,qdx)
                
                
            def distance_cost(nodes_list):
                return np.mean([self.gate_ids.index(node_id)-self.gate_ids.index(nodes_list[0]) for node_id in nodes_list])
            continue_group = []
            continue_remote_gates = []
            group_sign_key = []
            for node_id in self.remote_gates[jdx][idx]:
                iidx = nodes.index(node_id)
                if node_id not in flatten_list(continue_group):
                    con0 = iter_continue0(iidx,self.gate_set[node_id].qubits[0].index)
                    conR0 = [node_id for node_id in con0 if node_id in self.remote_gates[jdx][idx]]
                    con1 = iter_continue1(iidx,self.gate_set[node_id].qubits[1].index)
                    conR1 = [node_id for node_id in con1 if node_id in self.remote_gates[jdx][idx]]
                    chosen = 0
                    if len(conR1)> len(conR0):
                        chosen = 1
                    elif len(conR1)< len(conR0):
                        chosen =0
                    elif distance_cost([node_id] +con0)> distance_cost([node_id] +con1):
                        chosen = 1
                    else:
                        chosen = 0
                    if chosen:
                        for nid in con1[::-1]:
                            if nid not  in self.remote_gates[jdx][idx]:
                                con1.remove(nid)
                            else:
                                break
                        front_continue = get_front1(iidx, self.gate_set[node_id].qubits[1].index)
                        continue_group.append(front_continue+[node_id] +con1)
                        continue_remote_gates.append([node_id] +conR1)
                        
                        group_sign_key.append(-self.gate_set[node_id].qubits[1].index-1)
                    else:
                        for nid in con0[::-1]:
                            if nid not  in self.remote_gates[jdx][idx]:
                                con0.remove(nid)
                            else:
                                break
                        front_continue = get_front0(iidx, self.gate_set[node_id].qubits[0].index)
                        continue_group.append(front_continue+[node_id] +con0)
                        continue_remote_gates.append([node_id] +conR0)
                        group_sign_key.append(self.gate_set[node_id].qubits[0].index+1)
            
            continue_group = {i:g for i,g in enumerate(continue_group)}
            # return continue_group
            def check_group(gr):
                for g in  gr:
                    if self.gate_set[g].operation.name == 'cx' and g not in self.remote_gates[jdx][idx]:
                        return False
                return True
            def push_other_back(continue_group:list):
                end_group = []
                drop_num = 0
                for g in continue_group:
                    if g not in self.remote_gates[jdx][idx]:
                        drop_num+=1
                        end_group.append(g)
                for g in end_group:
                    continue_group.remove(g)
                    self.gate_ids.remove(g)
                
                location = self.gate_ids.index(continue_group[-1])
                for g in end_group:
                    self.gate_ids.insert(location+1,g)

            def push_other_front(continue_group:list):
                end_group = []
                # print([node.operation.index for node in continue_group])
                drop_num = 0
                for g in continue_group:
                    if g not in self.remote_gates[jdx][idx]:
                        drop_num+=1
                        end_group.append(g)
                for g in end_group:
                    continue_group.remove(g)
                    self.gate_ids.remove(g)
                location = self.gate_ids.index(continue_group[0])
                for g in end_group:
                    self.gate_ids.insert(location,g)
            
            group_key = [abs(k)-1 for k in group_sign_key]
            unique_k = reduce(lambda x, y: x + [y] if y not in x else x, group_key, [])
            reduce_group = {k:[] for k in unique_k}
            reduce_num = {k:0 for k in unique_k}
            reduce_map = {}
            type_map = []
            for i,g in  continue_group.items():
                reduce_group[group_key[i]].append(g)
                reduce_map[(group_key[i],len(reduce_group[group_key[i]])-1)]= i
                reduce_num[group_key[i]]+=1
            need_reduce_nums = []
            
            def group_continue_group(k,i,accumulate_num):
                for m in range(1,accumulate_num):
                    ## concat the continue_group
                    continue_group[reduce_map[(k,i+1-accumulate_num)]] += continue_group[reduce_map[(k,i+1-accumulate_num+m)]] 
                    ## delete the continue_group
                    del continue_group[reduce_map[(k,i-accumulate_num+1+m)]]
                type_map.append(reduce_map[(k,i+1-accumulate_num)])
                

            def get_wire_gate(str,end,wire):
                nodes_on_wire = []
                for node_id in self.gate_ids:
                    wires = [q.index for q in self.gate_set[node_id].qubits]
                    if node_id >=str and node_id <end and wire in wires:
                        nodes_on_wire.append(node_id)
                return nodes_on_wire
            
            for k,num in reduce_num.items():
                if num > 2:
                    need_reduce_nums.append(k)

            
            for k in need_reduce_nums:
                accumulate_num = 0
                for i in range(len(reduce_group[k])):
                    if check_group(reduce_group[k][i]):
                        accumulate_num+=1
                        if i >= len(reduce_group[k])-1:
                            if accumulate_num>1:
                                group_continue_group(k,i,accumulate_num)
                            accumulate_num =0
                            break
                    elif accumulate_num ==0:
                        push_other_front(continue_group[reduce_map[(k,i)]])
                    else:
                        push_other_back(continue_group[reduce_map[(k,i)]])
                        if accumulate_num>1:
                            accumulate_num+=1
                            group_continue_group(k,i,accumulate_num)
                        accumulate_num =0
                    if i+1 >= len(reduce_group[k]):
                        break
                    str = reduce_group[k][i][-1]
                    end = reduce_group[k][i+1][0]
                    
                    wire_nodes = get_wire_gate(str,end,k)
                    if not check_group(wire_nodes):
                        if accumulate_num>1:
                            group_continue_group(k,i,accumulate_num)
                        accumulate_num =0
            self.remote_group[(jdx,idx)]=continue_group
            self.remote_map[(jdx,idx)] = type_map
            self.qtele_map[(jdx,idx)] = group_sign_key
        return self.remote_group
    def insert_epr_label(self,group:list,qt:int,qubit:Qubit,type:str):
        """插入epr 门

        Args:
            group (list):  the gate needs to be transport to another qpu
            qt (int):  the qubit index
            qubit (Qubit): the qubit object
            type (str):  telegate or teledata
        """        
        str = self.gate_ids.index(group[0])
        eprgatef= EPRGate(type,qt,[qubit],0).get_gate()
        self.gate_set.append(eprgatef)
        self.gate_max_id+=1
        self.gate_ids.insert(str,self.gate_max_id)
        end = self.gate_ids.index(group[-1])
        eprgateb = EPRGate(type,qt,[qubit],1).get_gate()
        self.gate_set.append(eprgateb)
        self.gate_max_id+=1
        eprgatef.operation.end = self.gate_max_id
        self.gate_ids.insert(end+1,self.gate_max_id)

    def insert_epr(self):
        """插入epr门
        将获得的远程门的组,分别在前后插入epr门
        """
        def resort_continue_gates(group:list,qtele,remote_key):
            end_group = []
            if qtele> 0:
                qt = qtele-1
                assert self.gate_set[group[0]].qubits[0].index ==  qt
                ## 将所有RZ的门放到最前面
                phiz = 0
                for g in group:
                    if self.gate_set[g].operation.name == 'rz':
                        phiz += float(self.gate_set[g].operation.params[0])
                        end_group.append(g)
                for g in end_group:
                    group.remove(g)
                    self.gate_ids.remove(g)
                location = self.gate_ids.index(group[0])
                phiz = float(phiz)
                phiz = phiz - phiz//np.pi*np.pi
                if phiz != 0:
                    rzgate = CircuitInstruction(RZGate(phiz),[self.gate_set[group[0]].qubits[0]],[])
                    self.gate_set.append(rzgate)
                    self.gate_max_id+=1
                    self.gate_ids.insert(location,self.gate_max_id)
                ## 将所有的X门放到最后面,并在CNOT的控制比特上加上X门
                x_num = 0
                x_gate_remove = []
                x_gate_map = {i:0 for i in range(len(group))}
                for gi,g in enumerate(group):
                    if self.gate_set[g].operation.name == 'x':
                        x_gate_remove.append(g)
                        x_num+=1
                        for gj in range(gi+1,len(group)):
                            if self.gate_set[group[gj]].operation.name == 'cx':
                                x_gate_map[gj] = 1-x_gate_map[gj]
                
                ## 插入X门
                for i in range(len(group)):
                    if x_gate_map[i]:
                        
                        xgate1 = CircuitInstruction(XGate(),[self.gate_set[group[i]].qubits[1]],[])
                        self.gate_set.append( xgate1)
                        self.gate_max_id+=1
                        #print('insert x gate,qubits:',self.gate_set[group[i]].qubits[0].index,self.gate_set[group[i]].qubits[1].index,'postion:',self.gate_ids.index(group[i])+1)
                        self.gate_ids.insert(self.gate_ids.index(group[i])+1,self.gate_max_id)
                
                for g in x_gate_remove:
                    group.remove(g)
                    self.gate_ids.remove(g)
                
                if x_num%2 == 1:
                    ## 如果X门的数量为奇数，则在最后一个CNOT的控制比特上加上X门
                    xgate = CircuitInstruction(XGate(),[self.gate_set[group[0]].qubits[0]],[])
                    self.gate_set.append( xgate)
                    self.gate_max_id+=1
                    self.gate_ids.insert(self.gate_ids.index(group[-1])+1,self.gate_max_id)
                ## 将所有的非远程CNOT门放到前面
                end_group = []
                for g in group:
                    if g not in self.remote_gates[remote_key[0]][remote_key[1]]:
                        end_group.append(g)
                for g in end_group:
                    group.remove(g)
                    self.gate_ids.remove(g)
                
                location = self.gate_ids.index(group[0])
                for g in end_group:
                    self.gate_ids.insert(location,g)
                
                
            else:
                drop_num = 0
                qt = -qtele -1
                assert self.gate_set[group[0]].qubits[1].index ==  qt
                for g in group:
                    if self.gate_set[g].operation.name == 'sx':
                        drop_num+=1
                        end_group.append(g)
                    if self.gate_set[g].operation.name == 'x':
                        drop_num +=2
                        end_group.append(g)
                     
                
                for g in end_group: 
                    group.remove(g)
                    self.gate_ids.remove(g)
                location = self.gate_ids.index(group[0])
                qubit_= self.gate_set[group[0]].qubits[1]
                if drop_num%4 ==1:
                    gatenew = CircuitInstruction(SXGate(),[qubit_],[])
                    self.gate_set.append(gatenew)
                    self.gate_max_id+=1
                    self.gate_ids.insert(location,self.gate_max_id)

                elif drop_num%4 ==2:
                    gatenew = CircuitInstruction(XGate(),[qubit_],[])
                    self.gate_set.append(gatenew)
                    self.gate_max_id+=1
                    self.gate_ids.insert(location,self.gate_max_id)
                elif drop_num%4 ==3:
                    gatenew = CircuitInstruction(XGate(),[qubit_],[])
                    self.gate_set.append(gatenew)
                    self.gate_max_id+=1
                    self.gate_ids.insert(location,self.gate_max_id)
                    gatenew = CircuitInstruction(SXGate(),[qubit_],[])
                    self.gate_set.append(gatenew)
                    self.gate_max_id+=1
                    self.gate_ids.insert(location,self.gate_max_id)
                
                # 将所有的非远程CNOT门放到前面
                end_group = []
                for g in group:
                    if g not in self.remote_gates[remote_key[0]][remote_key[1]]:
                        end_group.append(g)
                for g in end_group:
                    group.remove(g)
                    self.gate_ids.remove(g)
                location = self.gate_ids.index(group[0])
                for g in end_group:
                    self.gate_ids.insert(location,g)
                
                ## 改变每个CNOT 的方向
                for g in group:
                    self.gate_set[g].qubits = self.gate_set[g].qubits[::-1]
                
                
                ## 前后各加一个H门
                gatenew = self.get_h_gate(qubit_)
                location = self.gate_ids.index(group[0])
                for gid in gatenew:
                    self.gate_ids.insert(location,gid)
                gatenew = self.get_h_gate(qubit_)
                location = self.gate_ids.index(group[-1])
                for gid in gatenew:
                    self.gate_ids.insert(location+1,gid)


        for key in self.remote_group:
            group = self.remote_group[key]
            for gidx in group:
                qt = abs(self.qtele_map[key][gidx])-1
                sign = 0 if self.qtele_map[key][gidx]>0 else 1
                qubit = self.gate_set[group[gidx][0]].qubits[0] if len(self.gate_set[group[gidx][0]].qubits)==1 else self.gate_set[group[gidx][0]].qubits[sign]
                if gidx in self.remote_map[key]:
                    self.insert_epr_label(group[gidx],qt,qubit,'teledata')
                else:
                    resort_continue_gates(group[gidx],self.qtele_map[key][gidx],key)
                    self.insert_epr_label(group[gidx],qt,qubit,'telegate')
                
    def get_compile_circuit(self):
        """
        返回插入epr后的电路
        """
        testcircuit= self.circuit.copy()
        testcircuit.data = [self.gate_set[i] for i in self.gate_ids]
        self.epr_circuit = testcircuit
        return testcircuit
    def create_telegate_front(self,start_idx):
        """
        在start_idx前面插入一个teleportation,采用telegate 方式
        """
        gate = self.gate_set[start_idx]
        qubit = gate.qubits[0]
        end_idx = gate.operation.end
        sdx = self.gate_ids.index(start_idx)
        edx = self.gate_ids.index(end_idx)
        EPRs = QuantumRegister(2,'eprGateq'+str(self.epr_reg_num))
        self.newcircuit.add_register(EPRs)
        self.newcircuit.h(EPRs[0])
        self.newcircuit.cx(EPRs[0],EPRs[1])
        self.newcircuit.cx(qubit,EPRs[0])
        EPRClbits = ClassicalRegister(2,'eprGatec'+str(self.epr_reg_num))
        self.newcircuit.add_register(EPRClbits)
        self.newcircuit.measure(EPRs[0],EPRClbits[0])
        self.newcircuit.x(EPRs[1]).c_if(EPRClbits[0],1)
        for i in self.gate_ids[sdx:edx+1]:
            gate = self.gate_set[i]
            if len(gate.qubits)==2 and gate.qubits[0]==qubit:
                gate.qubits = (EPRs[1],gate.qubits[1])
        end_gate = self.gate_set[end_idx]
        end_gate.operation.EPRs = EPRs
        end_gate.operation.EPRClbits = EPRClbits
        self.epr_reg_num+=1
    def create_telegate_back(self,end_idx):
        """
        在end_idx后面插入一个teleportation,采用telegate 方式
        """
        gate  = self.gate_set[end_idx]
        qubit = gate.qubits[0]
        EPRs = gate.operation.EPRs
        EPRClbits = gate.operation.EPRClbits
        self.newcircuit.h(EPRs[1])
        self.newcircuit.measure(EPRs[1],EPRClbits[1])
        self.newcircuit.z(qubit).c_if(EPRClbits[1],1)
    def get_epr_num(self):
        """
        返回所需的epr纠缠对数量
        """
        if self.epr_circuit:
            return np.sum([gate.operation.value for gate in self.epr_circuit.data if gate.operation.name == 'epr'])
    def create_teledata_front(self,start_idx):
        """
        在start_idx前面插入一个teleportation,采用teledata 方式
        """
        gate = self.gate_set[start_idx]
        qubit = gate.qubits[0]
        end_idx = gate.operation.end
        sdx = self.gate_ids.index(start_idx)
        edx = self.gate_ids.index(end_idx)
        EPRs = QuantumRegister(2,'eprDataq'+str(self.epr_reg_num))
        EPRClbits = ClassicalRegister(2,'eprDatac'+str(self.epr_reg_num))
        self.newcircuit.add_register(EPRs)
        self.newcircuit.add_register(EPRClbits)
        self.newcircuit.h(EPRs[0])
        self.newcircuit.cx(EPRs[0],EPRs[1])
        self.newcircuit.cx(qubit,EPRs[0])
        self.newcircuit.h(qubit)
        self.newcircuit.measure(EPRs[0],EPRClbits[0])
        self.newcircuit.measure(qubit,EPRClbits[1])
        self.newcircuit.x(EPRs[1]).c_if(EPRClbits[0],1)
        self.newcircuit.z(EPRs[1]).c_if(EPRClbits[1],1)

        for i in self.gate_ids[sdx+1:edx]:
            gate = self.gate_set[i]
            if len(gate.qubits)==2:
                if gate.qubits[0]==qubit:
                    gate.qubits = (EPRs[1],gate.qubits[1])
                if gate.qubits[1]==qubit:
                    gate.qubits = (gate.qubits[0],EPRs[1])
            elif gate.qubits[0]==qubit:
                gate.qubits = (EPRs[1],)
        
        end_gate = self.gate_set[end_idx]
        end_gate.operation.dataqubit = EPRs[1]
        self.epr_reg_num+=1
        
    def create_teledata_back(self,end_idx):
        """
        在end_idx后面插入一个teleportation,采用teledata 方式
        """
        gate = self.gate_set[end_idx]
        qubit = gate.qubits[0]
        dataqubit = gate.operation.dataqubit
        EPRs = QuantumRegister(2,'eprDataq'+str(self.epr_reg_num))
        EPRClbits = ClassicalRegister(2,'eprDatac'+str(self.epr_reg_num))
        self.newcircuit.add_register(EPRs)
        self.newcircuit.add_register(EPRClbits)
        self.newcircuit.cx(dataqubit,EPRs[1])
        self.newcircuit.h(dataqubit)
        self.newcircuit.measure(EPRs[1],EPRClbits[0])
        self.newcircuit.measure(dataqubit,EPRClbits[1])
        self.newcircuit.x(EPRs[0]).c_if(EPRClbits[0],1)
        self.newcircuit.z(EPRs[0]).c_if(EPRClbits[1],1)
        self.epr_reg_num+=1
        qidx = self.qubit_map.index(qubit)
        self.qubit_map[qidx] = EPRs[0]
        edx = self.gate_ids.index(end_idx)
        for i in self.gate_ids[edx:]:
            gate = self.gate_set[i]
            if len(gate.qubits)==2:
                if gate.qubits[0]==qubit:
                    gate.qubits = (EPRs[0],gate.qubits[1])
                if gate.qubits[1]==qubit:
                    gate.qubits = (gate.qubits[0],EPRs[0])
            elif gate.qubits[0]==qubit:
                gate.qubits = (EPRs[0],)

    def compile_with_teleportion(self):
        """
        采用teleportation方式编译
        """
        self.newcircuit = self.epr_circuit.copy_empty_like()
        self.qubit_map = deepcopy(self.newcircuit.qubits)
        for gateid in self.gate_ids:
            gate = self.gate_set[gateid]
            if gate.operation.name == 'epr':
                if gate.operation.label == 'f':
                    if gate.operation.value == 0.5:
                        self.create_telegate_front(gateid)
                    else:
                        self.create_teledata_front(gateid)
                if gate.operation.label == 'b':
                    if gate.operation.value == 0.5:
                        self.create_telegate_back(gateid)
                    else:
                        self.create_teledata_back(gateid)
            else:
                self.newcircuit.data.append(gate)
        self.add_measure()
        self.newcircuit= self.compileToBackend(self.newcircuit)
        return self.newcircuit
    def add_measure(self):
        """
        添加测量
        """
        measure_bits = ClassicalRegister(len(self.qubit_map), "data")
        self.newcircuit.add_register(measure_bits)
        for i,qubit in enumerate(self.qubit_map):
            self.newcircuit.measure(qubit,measure_bits[i])
    def compileToBackend(self,circuit):
        """
        采用qiskit的transpile方法编译
        """
        from qiskit.transpiler.passes import Optimize1qGates,Collect2qBlocks
        from qiskit.transpiler import PassManager
        from qiskit.compiler import transpile
        qc_transpiled = transpile(circuit, basis_gates=['id','x','sx','rz','cx'],optimization_level=3)
        pass_ = PassManager([Optimize1qGates(),Collect2qBlocks()])
        qc_optimized = pass_.run(qc_transpiled)
        return qc_optimized
    
if __name__ == '__main__':
    from qiskit import QuantumCircuit
    import numpy as np
    circuit = QuantumCircuit(4,4)
    circuit.cx(1,0)
    circuit.cx(2,0)
    circuit.cx(0,2)
    circuit.cx(1,2)
    circuit.cx(2,3)
    circuit.cx(1,0)
    circuit.cx(2,0)
    circuit.x(1)
    circuit.cx(3,0)
    circuit.cx(0,2)
    circuit.cx(1,0)
    circuit.h(3)
    circuit.cx(0,3)

    circuit.draw('mpl')
    partCom= Partcompile(circuit,[0,0,1,1],compile=True)
    newcircuit = partCom.run()
    newcircuit.draw('mpl',filename='newcircuit.png')
