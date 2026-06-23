# 量子电路分割-量子网络
## 背景介绍
量子网络通信在电路分割层面为门的分割，也就是把比特看成点，门看成边进行最小通信代价，子图有最大顶点数限制的分割；
通信代价定义为实现远程门连接的EPR纠缠对数目。
一般情况下，一个远程门（也就是不同量子芯片的比特间的门操作）对应一个EPR纠缠对，当存在一个比特和一个芯片间的通信时，这些连续作用的门都可以当作一个Block，可以被一个EPR纠缠对实现
![](./imgs/block.png)
因此对应的图割问题的的最优代价为EPR纠缠对的数目。

经典的FM算法
<https://limsk.ece.gatech.edu/book/slides/pdf/FM-partitioning.pdf>

<https://github.com/kshitij1489/Graph-Partitioning>
图割问题的一些开源算法：
<https://github.com/iMoonLab/THU-HyperG>
图神经网络的算法 ：
<https://github.com/microsoft/graph-partition-neural-network-samples>
## 获得连接图
1. 约化操作
2. 获得表示比特连接性的矩阵
已经在代码 [partdqc](../src/core/assignQubit/partdqc.py) 里实现了，每一层的邻接矩阵都可以获得

## 贪心局部搜索算法
1. 构建量子比特连接表
2. 改进的FM算法启发式二分求解最优解
3. 对最后的结果微调
   针对提高时延和保真度的微调。
## 其他可能算法实现
1. 数学规划
    感觉优化目标不好写，决策变量是很容易定义的，不过要事先制定好子电路总数
2. 一般意义的图割算法（目标函数为不考虑Block cost效应时芯片间连接门的数量，hypergraph 的切割边数）得到多个次优解，再考虑block 效应后的，从次优解中选择最优的解。

