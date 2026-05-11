"""此文件将废弃 this file will be deprecated"""
from qiskit.converters import circuit_to_dag
from qiskit.circuit import QuantumCircuit
import os
import matplotlib.pyplot as plt
import networkx as nx
from typing import Iterable
import numpy as np
from itertools import combinations
class QubitNetwork:
    def __init__(self, circuit, resultDir):
        self.circuit = circuit
        self.resultDir = resultDir
        self.qubit_map = []
        self.dag = circuit_to_dag(self.circuit)
    def qubit_connected_list(self):
        """获得约化后的比特连接表
        self.qubit_map[i] 表示编号为i 的比特对应的qubit 对象
        Returns:
            list[list[int]]: list[i] 表示 第i 个比特所连接的其他比特的列表
        """
        self.qubit_map = []
        qcs = []
        for q in self.circuit.qubits:
            self.qubit_map.append(q)
            qtargets = []
            for op in self.dag.nodes_on_wire(q):
                if len(op.qargs) > 2:
                    raise ValueError(
                        "the circuit has a more than two qubit gate ")
                elif len(op.qargs) == 1:
                    raise ValueError(
                        "the dagcircuit haven't reduced completely ")
                qs = list(op.qargs)
                qs.remove(q)
                qtargets.append(qs[0]._index)
            qcs.append(qtargets)
        return qcs
    def cleanDir(self, dir: str):
        """清空文件夹
        """
        import shutil
        import platform
        self.system = platform.system()
        if not os.path.exists(dir):
            os.makedirs(dir)
        else:
            shutil.rmtree(dir)
    def connect_matrixs(self) -> Iterable:
        """获得每层的邻接矩阵

        Returns:
            List: List[i] 表示第i层的邻接矩阵
        """
        # 每一层的比特间邻接矩阵
        connections = []
        for layer in self.dag.layers():
            connectM = np.zeros((self.dag.num_qubits(), self.dag.num_qubits()))
            for node in list(layer['graph'].op_nodes()):
                for i, j in combinations(node.qargs, 2):
                    connectM[i.index][j.index] = 1
                    connectM[j.index][i.index] = 1
            connections.append(connectM)
        return connections

    def draw_network(self, G, filePath):

        e_one = [(u, v)
                    for (u, v, d) in G.edges(data=True) if d["weight"] == 1]
        e_more = [(u, v)
                    for (u, v, d) in G.edges(data=True) if d["weight"] > 1]

        # positions for all nodes - seed for reproducibility
        pos = nx.circular_layout(G)
        # nodes
        nx.draw_networkx_nodes(G, pos, node_size=700)
        # edges
        nx.draw_networkx_edges(G, pos, edgelist=e_more, width=6)
        nx.draw_networkx_edges(
            G, pos, edgelist=e_one, width=6, alpha=0.5, edge_color="b", style="dashed"
        )

        # node labels
        nx.draw_networkx_labels(G, pos, font_size=20, font_family="sans-serif")
        # edge weight labels
        edge_labels = nx.get_edge_attributes(G, "weight")
        nx.draw_networkx_edge_labels(G, pos, edge_labels)

        ax = plt.gca()
        ax.margins(0.08)
        plt.axis("off")
        plt.tight_layout()
        plt.show()
        plt.savefig(filePath)

    def final_connect_matrix(self, draw=False):
        # 电路的总体连接矩阵并绘图
        Matrix = sum(self.connect_matrixs())
        if draw:
            G = nx.from_numpy_matrix(Matrix)
            self.draw_network(G, self.resultDir+"/final_con.png")
        return Matrix

    def draw_connection(self):
        # 绘制每层的比特连接图
        connections = self.connect_matrixs()
        fileDir = self.resultDir+"/connect_net"
        if not os.path.exists(fileDir):
            os.makedirs(fileDir)

        for index, matrix in enumerate(np.add.accumulate(connections)):
            self.draw_network(nx.from_numpy_matrix(matrix),
                                fileDir+"/{}-layer.png".format(index))
