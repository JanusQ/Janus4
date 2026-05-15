from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit
import numpy as np
from qram.qramtemplate.bucktele import Qram

class RouterQubit:
    def __init__(self, x, y, level, direction):
        self.x = x
        self.y = y
        self.level = level
        self.left_router = None
        self.right_router = None
        self.left = None
        self.right = None
        self.root = None
        self.direction = direction
        self.qreg = QuantumRegister(1,self.reg_name)

    def add_left(self,pos_x, pos_y):
        self.left = RouterQubit(pos_x, pos_y,self.level+1, self.direction + '0')
        self.left.parent = self.left_router
        self.left_router.next = self.left
    
    def add_right(self,pos_x, pos_y):
        self.right = RouterQubit(pos_x, pos_y, self.level+1, self.direction + '1')
        self.right.parent = self.right_router
        self.right_router.next = self.right
    
    def add_left_router(self, pos_x, pos_y):
        self.left_router = RouterQubit(pos_x, pos_y,  self.level+1, self.direction + 'l')
        self.left_router.parent = self
    
    def add_right_router(self, pos_x, pos_y):
        self.right_router = RouterQubit(pos_x, pos_y,  self.level+1, self.direction + 'r')
        self.right_router.parent = self
        
        
        

    @property
    def address(self):
        if self.root is None:
            return self.direction
        else:
            return self.root.address + self.direction

    @property
    def reg_name(self):
        if self.address:
            return f"router_{self.level}_{self.address}"
        else:
            return f"router_{self.level}"

    def add_leaf_qubits(self, circuit):
        self.left =  QuantumRegister(1,self.reg_name + '_l')
        self.right =  QuantumRegister(1,self.reg_name + '_r')
        circuit.add_register(self.left)
        circuit.add_register(self.right)
    
    def add_data_qubits(self, circuit):
        self.data =  QuantumRegister(1,self.reg_name + '_data')
        circuit.add_register(self.data)

class IncidentQubit:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.qreg = QuantumRegister(1,'incident')
        self.left = None
        self.right = None
        self.parent = None
        self.left_router = None
        self.right_router = None
        self.address = 'incident'


class AddressQubits:
    def __init__(self, levels):
        self.qregs = QuantumRegister(levels,f"address")

class AddressQubit:
    def __init__(self, x, y, level, Qregs):
        self.x = x
        self.y = y
        self.level = level
        self.qreg = Qregs[level]
    
    
class BusQubit:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.qreg = QuantumRegister(1,'bus')


def map_h_tree_to_grid(node: RouterQubit, x, y, length, depth):
    """
    递归地将 H 树映射到网格。

    :param x: 当前 H 树的中心 x 坐标
    :param y: 当前 H 树的中心 y 坐标
    :param length: 当前 H 树的水平线段长度
    :param depth: 剩余的递归深度（可以是半整数）
    :param result: 存储线段起点和终点的列表
    :param grid_mapping: 存储 H 树顶点与网格格点映射关系的字典
    :return: 返回当前节点
    """
    if depth <= 0:
        node.min_length = length/2
        return None

    half_length = length / 2

    # 当前 H 的线段坐标
    left_x = x - half_length
    half_left_x = x - half_length/2
    right_x = x + half_length
    half_right_x = x + half_length/2
    
    top_y = y + half_length
    half_top_y = y + half_length/2
    bottom_y = y - half_length
    half_bottom_y = y - half_length/2
    
    if depth*2 % 2 == 0 and depth > 1:
        left_x = left_x + half_length/4
        # half_left_x = half_left_x + half_length/4
        right_x = right_x - half_length/4
        # half_right_x = half_right_x - half_length/4
    elif depth*2 % 2 == 1 and depth > 2:
        pass
        top_y = top_y - half_length/4
        # half_top_y = half_top_y - half_length/2
        bottom_y = bottom_y + half_length/4
        # half_bottom_y = half_bottom_y + half_length/2
        

    # 水平线段
    if depth == 0.5:
        node.add_left_router(left_x, y)
        node.add_left(left_x,node.parent.y)
        # 右垂直线段
        node.add_right_router(right_x, y)
        node.add_right(right_x,node.parent.y)
        node.min_length = abs(y-node.parent.y)
        node.left.min_length = node.min_length
        node.right.min_length = node.min_length
        node.left_router.min_length = node.min_length
        node.right_router.min_length = node.min_length
        return node
    # 左垂直线段
    node.add_left_router(half_left_x, y)
    node.add_left(left_x,y)
    # 右垂直线段
    node.add_right_router(half_right_x, y)
    node.add_right(right_x,y)
    if depth > 1:
        node.left.add_left_router(left_x, half_bottom_y)
        node.left.add_left(left_x, bottom_y)
        map_h_tree_to_grid(node.left.left,left_x, bottom_y, length / 2, depth - 1)  # 左下
        
        node.left.add_right_router(left_x, half_top_y)
        node.left.add_right(left_x, top_y)
        map_h_tree_to_grid(node.left.right,left_x, top_y, length / 2, depth - 1)
        
        node.right.add_left_router(right_x, half_bottom_y)
        node.right.add_left(right_x, bottom_y)
        map_h_tree_to_grid(node.right.left,right_x, bottom_y, length / 2, depth - 1) # 右下
        
        node.right.add_right_router(right_x, half_top_y)
        node.right.add_right(right_x, top_y)
        map_h_tree_to_grid(node.right.right,right_x, top_y, length / 2, depth - 1) # 右上
    if depth == 1:
        node.left.add_left_router(left_x, bottom_y)
        node.left.add_left(node.left.parent.x, bottom_y)
        map_h_tree_to_grid(node.left.left,left_x, bottom_y, length / 2, depth - 1)  # 左下
        node.left.add_right_router(left_x, top_y)
        node.left.add_right(node.left.parent.x, top_y)
        map_h_tree_to_grid(node.left.right,left_x, top_y, length / 2, depth - 1)
        
        node.right.add_left_router(right_x, bottom_y)
        node.right.add_left(node.right.parent.x, bottom_y)
        map_h_tree_to_grid(node.right.left,right_x, bottom_y, length / 2, depth - 1) # 右下
        
        node.right.add_right_router(right_x, top_y)
        node.right.add_right(node.right.parent.x, top_y)
        map_h_tree_to_grid(node.right.right,right_x, top_y, length / 2, depth - 1) # 右上
        
    node.min_length = node.left.left.min_length
    node.left.min_length = node.min_length
    node.right.min_length = node.min_length
    return node

def plot_binary_tree(root):
    """
    绘制生成的二叉树结构。
    :param root: 二叉树的根节点
    """
    def add_edges(node, edges, positions):
        if not node:
            return
        positions[node] = (node.x, node.y)
        if node.left_router:
            positions[node.left_router] = (node.left_router.x, node.left_router.y)
            edges.append(((node.x, node.y), (node.left_router.x, node.left_router.y)))
        if node.right_router:
            positions[node.right_router] = (node.right_router.x, node.right_router.y)
            edges.append(((node.x, node.y), (node.right_router.x, node.right_router.y)))
        if node.left:
            positions[node.left] = (node.left.x, node.left.y)
            if node.left_router:
                edges.append(((node.left_router.x, node.left_router.y), (node.left.x, node.left.y)))
            else:
                edges.append(((node.x, node.y), (node.left.x, node.left.y)))
            add_edges(node.left, edges, positions)
        if node.right:
            positions[node.right] = (node.right.x, node.right.y)
            if node.right_router:
                edges.append(((node.right_router.x, node.right_router.y), (node.right.x, node.right.y)))
            else:
                edges.append(((node.x, node.y), (node.right.x, node.right.y)))
            add_edges(node.right, edges, positions)

    edges = []
    positions = {}
    add_edges(root, edges, positions)

    fig = plt.figure(figsize=(15, 15))
    for (x1, y1), (x2, y2) in edges:
        plt.plot([x1, x2], [y1, y2], c='black')
    for node, (x, y) in positions.items():
        plt.scatter(x, y, c='blue')
        plt.text(x, y, str(node.address), fontsize=10, ha='center', va='center', color='white',
                 bbox=dict(facecolor='blue', edgecolor='none', boxstyle='circle,pad=0.3'))
    plt.gca().invert_yaxis()
    plt.grid(True, which='both', axis='both')
    plt.savefig(
        'binary_tree.png'
    )
    plt.show()

def update_positions(node,depth):
    """
    更新二叉树节点的坐标。
    :param root: 二叉树的根节点
    """
    xscale = 1 if 2*depth % 2 == 0 else 1
    yscale = 2 if 2*depth % 2 == 0 else 1
    node.x = node.x/node.min_length
    node.y = node.y/node.min_length
    node.x = node.x/xscale
    node.y = node.y/yscale
    if node.left_router:
        node.left_router.x = node.left_router.x/node.min_length/xscale
        node.left_router.y = node.left_router.y/node.min_length/yscale
    if node.right_router:
        node.right_router.x = node.right_router.x/node.min_length/xscale
        node.right_router.y = node.right_router.y/node.min_length/yscale
    if node.left:
        
        update_positions(node.left,depth)
    if node.right:
        
        update_positions(node.right,depth)

class Grid:
    def __init__(self, offset_x, offset_y,width, height):
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.width = int(width)
        self.height = int(height)
        self.layout = {}
        self.reverse_layout = {}
        
    def position_to_label(self, x, y):
        label = (x+self.offset_x)+(y+self.offset_y)*self.width
        if label < 0:
            raise ValueError(f"label should be non-negative ,wrong position ({x}, {y})")
        return int(label)
    def plot_grid_map(grid_map,level):
        """
        绘制平面方格图。
        :param grid_map: 格点映射的字典
        """
        plt.figure(figsize=(8, 8))
        for (x, y), node in grid_map.items():
            plt.scatter(x, y, c='blue')
            plt.text(x, y, str(node.value), fontsize=10, ha='center', va='center', color='white',
                    bbox=dict(facecolor='blue', edgecolor='none', boxstyle='circle,pad=0.3'))
            if node.parent:
                px, py = node.parent.position
                plt.plot([x, px], [y, py], c='black')

        plt.grid(True)
        plt.gca().set_aspect('equal', adjustable='box')
        plt.savefig(f'mapping_level_{level}.png')

    def generate_coupling_map(self):
        coupling_map = []
        for i in range(self.width):
            for j in range(self.height):
                if i < self.width - 1:
                    coupling_map.append([i+ j*self.width, i+1+ j*self.width])
                if j < self.height - 1:
                    coupling_map.append([i+ j*self.width, i+ (j+1)*self.width])
        return coupling_map
    
    def plot_coupling_map(self,layout=None):
        import matplotlib.pyplot as plt
        # 设置图形大小和字体
        plt.figure(figsize=(3.3, 2.5))  # 1/3 A4宽度，高度适当调整
        plt.rcParams['font.size'] = 8  # 全局字体大小
        plt.rcParams['font.family'] = 'Arial'
        plt.rcParams['xtick.labelsize'] = 8  # x轴刻度字体大小
        plt.rcParams['ytick.labelsize'] = 8  # y轴刻度字体大小
        plt.rcParams['axes.labelsize'] = 9  # 轴标签字体大小
        plt.rcParams['axes.titlesize'] = 10  # 标题字体大小
        if layout is None:
            for i in range(self.width):
                for j in range(self.height):
                    plt.text(i, j, str(i+j*self.width), ha='center', va='center', fontsize=12)
        else:
            for label, qreg in layout.items():
                x, y = label//self.width, label%self.width
                if hasattr(qreg, '_register'):
                    name = qreg._register.name
                else:
                    name = qreg.name
                plt.scatter(x,y,s=20,c='grey')
                plt.text(x, y, name, ha='center', va='center', fontsize=12)
                
        for edge in self.generate_coupling_map():
            plt.plot([edge[0]%self.width, edge[1]%self.width], [edge[0]//self.width, edge[1]//self.width], 'k-')
        plt.axis('off')
        plt.savefig('couplingmap.png')
        plt.show()
        pass

        
    def map_qubits_to_grid(self, node: RouterQubit):
        self.layout[self.position_to_label(node.x,node.y)] = node.qreg
        self.reverse_layout[node.qreg] = self.position_to_label(node.x,node.y)
        if node.left_router:
            self.layout[self.position_to_label(node.left_router.x,node.left_router.y)] = node.left_router.qreg
            self.reverse_layout[node.left_router.qreg] = self.position_to_label(node.left_router.x,node.left_router.y)
        if node.right_router:
            self.layout[self.position_to_label(node.right_router.x,node.right_router.y)] = node.right_router.qreg
            self.reverse_layout[node.right_router.qreg] = self.position_to_label(node.right_router.x,node.right_router.y)
        if node.left:
            self.map_qubits_to_grid(node.left)
        if node.right:
            self.map_qubits_to_grid(node.right)
        return self.layout


class ResourceEstimator:
    def __init__(self, depth):
        self.depth = depth
        self.swap_counts = 0
        self.swap_depth = [[] for i in range(depth+1)]
        self.tele_CZ_count = 0
        self.tele_CZ_depth = [[] for i in range(depth+1)]
    
    def calculate_swap_tele_count(self, root: RouterQubit, depth):
        if depth == self.depth:
            left_distance = abs(root.left.y - root.y)+abs(root.left.x - root.x)
            if left_distance > 1:
                self.swap_counts += left_distance-1
                self.tele_CZ_count += left_distance-1
                self.tele_CZ_depth[depth].append(2 if (left_distance-1)%2 ==1   else 3)
                self.swap_depth[depth].append(left_distance-1)
            self.calculate_swap_tele_count(root.left,depth-1)
            return
        if root.left is None and root.right is None:
            return
        if root.left is not None:
            left_distance = abs(root.left.y - root.y)+abs(root.left.x - root.x)
            if left_distance > 2:
                self.swap_counts += left_distance-2
                self.tele_CZ_count += left_distance-2
                self.tele_CZ_depth[depth].append(2 if (left_distance-2)%2 ==1   else 3)
                self.swap_depth[depth].append(left_distance-2)
            self.calculate_swap_tele_count(root.left,depth-1)
        if root.right is not None:
            right_distance = abs(root.right.y - root.y)+abs(root.right.x - root.x)
            if right_distance > 2:
                self.swap_counts += right_distance-2
                self.tele_CZ_count += right_distance-2
                self.tele_CZ_depth[depth].append(2 if (right_distance-2)%2 ==1   else 3)
                self.swap_depth[depth].append(right_distance-2)
            self.calculate_swap_tele_count(root.right,depth-1)
            
            
        
    def find_depth(self):
        tele_d = 0
        tele_c = 0
        swap_d = 0
        swap_c = 0
        for i in range(self.depth+1):
            if self.tele_CZ_depth[i]:
                tele_d += max(self.tele_CZ_depth[i])*(self.depth)*2
                swap_d += max(self.swap_depth[i])*(self.depth)*2
                tele_c += sum(self.tele_CZ_depth[i])*(self.depth)*2
                swap_c += sum(self.swap_depth[i])*(self.depth)*2
        return tele_c,swap_c,tele_d,swap_d
    




# 示例：生成 H 树网格
if __name__ == "__main__":
    from qiskit import transpile
    from qiskit.circuit import Qubit
    import matplotlib.pyplot as plt
    DEPTH = 3
    center_x, center_y = 0, 0  # H 树中心
    initial_length = 10  # 初始水平线段长度
    max_depth = (DEPTH-1)/2  # 最大递归深度（支持半整数）
    # 存储网格线段和映射关系
    incident_y = 2**(max_depth-0.5)+2**(max_depth-1.5) if max_depth*2 % 2 == 1 else 2**max_depth
    maxinum_x = incident_y+1 if max_depth*2 % 2 == 0 else incident_y
    maxinum_y = incident_y-1  if max_depth*2 % 2 == 0 else incident_y
    incident = IncidentQubit(0,incident_y)
    address_qregs = AddressQubits(max_depth*2+1).qregs
    root = map_h_tree_to_grid(RouterQubit(center_x,center_y,0,''),center_x, center_y, initial_length, max_depth)
    update_positions(root,max_depth)
    incident.left = root
    incident.min_length = root.min_length
        # plot_binary_tree(incident)    
    
    layout = {}
    grid = Grid(maxinum_x,maxinum_y, 2*maxinum_x+1, 2*maxinum_y+2)
    grid.map_qubits_to_grid(incident)
    
    coupling_map = grid.generate_coupling_map()
    print(grid.layout)
    addresses = []
    for i in range(int(max_depth*2+1)):
        addresses.append(AddressQubit(-i,incident_y,i,address_qregs))
        grid.layout[grid.position_to_label(addresses[-1].x,addresses[-1].y)] = addresses[-1].qreg
        grid.reverse_layout[addresses[-1].qreg] = grid.position_to_label(addresses[-1].x,addresses[-1].y)
    
    bus = BusQubit(1,incident_y)
    grid.layout[grid.position_to_label(bus.x,bus.y)] = bus.qreg
    grid.reverse_layout[bus.qreg] = grid.position_to_label(bus.x,bus.y)
    grid.plot_coupling_map(grid.layout)
    address = [bin(i)[2:].zfill(3) for i in range(8)]
    # data = [i / 8 for i in range(8)]
    data = [0,0,1,1,1,0,0,1]
    bus_cregs = ClassicalRegister(1, 'bus_classical')
    address_cregs = ClassicalRegister(max_depth*2+1, 'address_classical')
    bus_qregs = bus.qreg
    qram = Qram(address, data,address_qregs, bus.qreg, address_cregs,bus_cregs)
    qram.circuit.h(address_qregs[0])
    qram.circuit.h(address_qregs[1])
    qram.circuit.h(address_qregs[2])
    qram.add_incident_qubits(incident)
    qram.add_router_tree(0,root)
    qram(address_qregs, bus_qregs)
    qram.circuit.measure(bus_qregs,bus_cregs)
    qram.circuit.measure(address_qregs,address_cregs)
    print(qram.circuit.num_qubits)
    # print(qram.circuit.draw())
    print(qram.circuit.count_ops())
    print(qram.circuit.depth())
    mapping = {
    }
    for i,qreg in grid.layout.items():
        qubit = qreg if isinstance(qreg,Qubit) else qreg._bits[0]
        # mapping[qram.circuit.find_bit(qubit).index] = i
        mapping[qubit]=i
    transpiled_circuit = transpile(qram.circuit,coupling_map=coupling_map,basis_gates=['cswap','swap','h','x'],routing_method='basic',seed_transpiler=42)
    # print(transpiled_circuit.draw())
    print(transpiled_circuit.count_ops())
    print(transpiled_circuit.depth())
    # 可视化结果
    # update_positions(root)
    plot_binary_tree(root)
    
    
