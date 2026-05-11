import math
import random
from functools import reduce
import numpy as np
from ..util import QpuList2allocation
from ..OBJ import DQCObj

class PartitionParallel:
    def __init__(self, circuit, qpu):
        self.circuit = circuit
        self.width = circuit.num_qubits
        self.vertexes = [i for i in range(self.circuit.num_qubits)]
        self.md = qpu.width
        self.qpu = qpu
        self.qubits_position = [0 for _ in range(self.circuit.num_qubits)]
        self.qpu_index = 1

    def get_obj(self, corrent_state,obj_str):
        """
        计算当前状态的目标函数值
        """
        return DQCObj(self.circuit, corrent_state,self.qpu).get_obj_min( obj_str)
    
    def minimize_obj(self, left, right, unmoved_v, qubits_position, obj_str, num_left,Delta):
        """
        fm算法的目标函数，根据最小EPR损失来确定最小移动
        """
        current_obj = self.get_obj(qubits_position, obj_str)
        left_qpu = qubits_position[left[0]]
        right_qpu = qubits_position[right[0]]
        max_obj = -999999
        max_v = -1
        max_qubits_position = qubits_position
        for v in unmoved_v:
            tmp_l = left.copy()
            tmp_r = right.copy()
            new_qubits_position = qubits_position.copy()
            if v in left:
                new_qubits_position[v] = right_qpu
                tmp_l.remove(v)
                tmp_r.append(v)
            else:
                new_qubits_position[v] = left_qpu
                tmp_l.append(v)
                tmp_r.remove(v)
            if num_left -Delta  <= len(tmp_l) <= num_left+ Delta:
                obj = current_obj - \
                        self.get_obj(new_qubits_position, obj_str)
                if max_obj < obj:
                    max_obj = obj
                    max_v = v
                    max_qubits_position = new_qubits_position
        return max_v, max_obj, max_qubits_position

    def init_part(self, vertexes, opt, num_left):
        """
        初始化分区
        """
        left = vertexes[:num_left]
        right = vertexes[num_left:]
        qubits_position = self.qubits_position.copy()
        for r in right:
            qubits_position[r] = self.qpu_index
        objvalue = self.get_obj( qubits_position, opt)
        min_obj = objvalue
        min_left = left
        min_right = right
        for i in range(30):
            qubits_position = self.qubits_position.copy()
            random.shuffle(vertexes)
            left = vertexes[:num_left]
            right = vertexes[num_left:]
            for r in right:
                qubits_position[r] = self.qpu_index
            objvalue = self.get_obj( qubits_position, opt)
            if objvalue < min_obj:
                min_obj = objvalue
                min_left = left
                min_right = right
        return min_left, min_right

    def fiduccia_mattheyses(self, vertexes, opt='DataFlux'):
        """
        fm算法
        """
        k = math.ceil(len(vertexes) / self.md)
        num_v = len(vertexes)
        if k % 2 == 1:
            num_left = int(len(vertexes)*((k-1)//2)/k)
            num_left_full = (k - 1) // 2 * self.md
        else:
            num_left = len(vertexes) // 2
            num_left_full = k//2*self.md
        ## 计算上下界
        MaxDelta = k*self.md - num_v
        Delta_left = num_left_full - num_left
        Delta = MaxDelta - Delta_left
        Delta = Delta_left if Delta_left < Delta else Delta
        Delta = Delta if Delta > 0 else 1

        left, right = self.init_part(vertexes, opt, num_left)
        for r in right:
            self.qubits_position[r] = self.qpu_index
        # 移动所有没有移动的点
        unmoved_v = vertexes.copy()
        # 存储所有结果
        history = []
        gain_sum = 0
        current_qubits_position = self.qubits_position  # 记录当前点的位置
        history.append({
            'left': left.copy(),
            'right': right.copy(),
            'move_v': None,
            'gain': 0,
            'gain_sum': 0,
            'qubits_position': current_qubits_position
        })
        while unmoved_v:
            current_v, gain, current_qubits_position = self.minimize_obj(
                left, right, unmoved_v, current_qubits_position, opt, num_left,Delta)
            if current_v == -1:
                break
            unmoved_v.remove(current_v)
            gain_sum += gain
            # 移动点集
            if current_v in left:
                label = 'left'
            else:
                label = 'right'
            if label == 'left':
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
                'gain_sum': gain_sum,
                'qubits_position': current_qubits_position
            })
        self.qpu_index += 1
        history = [h for h in history if num_left_full>= len(h['left'])>= num_left_full -MaxDelta]
        return reduce(lambda x, y: x if x['gain_sum'] > y['gain_sum'] else y, history)

    def k_fiduccia_mattheyses(self, opt='DataFlux'):
        """
        将电路切分成小于等于md的子电路，返回每个子电路的qubit
        """
        result = []
        def k_f(vertexes):
            if len(vertexes) <= self.md:
                result.append(vertexes)
                return
            res = self.fiduccia_mattheyses(vertexes, opt)
            left = res['left']
            right = res['right']
            self.qubits_position = res['qubits_position']
            k_f((left))
            k_f((right))
        
        k_f(self.vertexes)
        return result


def FM(circuit, optimize,qpu):
    """
    fm算法
    """
    qubit_list = PartitionParallel(circuit,qpu).k_fiduccia_mattheyses( opt=optimize)
    allocation = QpuList2allocation(qubit_list)
    return allocation
