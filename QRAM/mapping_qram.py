import matplotlib.pyplot as plt
from collections import deque
import math
from copy import deepcopy
import numpy as np
from matplotlib.animation import FuncAnimation
from math import sqrt

MAX_WIDTH = 3  # 最大宽度

class Node:
    def __init__(self, value):
        self.value = value
        self.parent = None
        self.children = []
        self.position = None  # 格点坐标

    def __repr__(self):
        return f"node {self.value}"
    
    def add_leaf(self, node):
        self.children.append(node)
        node.parent = self

    def insert_router(self, node):
        temp_children = deepcopy(self.children)
        self.children = [node]
        node.parent = self
        node.children = temp_children
        for child in temp_children:
            child.parent = node
        

def build_complete_binary_tree(levels):
    """
    构建完全二叉树。
    :param levels: 二叉树层数
    :return: 根节点
    """
    if levels <= 0:
        return None

    root = Node('')
    queue = deque([root])
    current_value= 1
    for l in range(levels - 2):
        for _ in range(len(queue)):
            parent = queue.popleft()
            left_router = Node('R')
            left_leaf = Node(parent.value+'0')
            left_router.add_leaf(left_leaf)
            parent.add_leaf(left_router)
            queue.append(left_leaf)
            current_value += 1

            right_router = Node('R')
            # 创建右节点
            right_leaf = Node(parent.value+'1')
            right_router.add_leaf(right_leaf)
            parent.add_leaf(right_router)
            queue.append(right_leaf)
            current_value += 1

    return root

def bound_condition(x, y, *args):
    """
    边界条件。
    :param x: 目标坐标x
    :param y: 目标坐标y
    :param min_x: 最小x坐标
    :param max_x: 最大x坐标
    :param min_y: 最小y坐标
    :param max_y: 最大y坐标
    :return: 是否在边界内
    """
    if len(args) == 4:
        min_x, max_x, min_y, max_y = args
    elif len(args) == 2:
        min_x, max_x = -args[0], args[0]
        min_y, max_y = -args[1], args[1]
    elif len(args) == 1:
        min_x, max_x = -args[0], args[0]
        min_y, max_y = -args[0], args[0]
    else:
        raise ValueError("Invalid arguments")
    return min_x <= x <= max_x and min_y <= y <= max_y



        

def angle_in_range(angle, min_angle, max_angle):
    """
    检查角度是否在范围内。
    :param angle: 目标角度
    :param min_angle: 最小角度
    :param max_angle: 最大角度
    :return: 是否在范围内
    """
    while angle < -math.pi:
        angle += 2 * math.pi
    while angle > math.pi:
        angle -= 2 * math.pi
    return min_angle < angle <= max_angle


def map_binary_tree_to_grid(root: Node):
    """
    将二叉树映射到二维正方格点，并生成动态的图像。
    :param root: 二叉树的根节点
    :return: 格点映射的字典
    """
    if not root:
        return {}

    grid_map = {}
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 上、右、下、左
    queue = deque([(root, (0, 0), -math.pi, math.pi)])  # (节点, 坐标, 最小角度, 最大角度)

    # 存储绘图数据
    plot_data = []

    # 存储每个节点的路径探索情况
    explored_positions = []

    while queue:
        node, position, min_angle, max_angle = queue.popleft()
        x, y = position
        if node is None:
            continue
        # 设置节点的位置并更新格点映射
        node.position = position
        grid_map[position] = node
        plot_data.append((x, y, node))  # 存储节点数据

        # 记录探索路径
        explored_positions.append((x, y, min_angle, max_angle))

        node_children_size = len(node.children)
        if node_children_size == 0:
            continue
        elif node_children_size == 1:
            valid_pos = []
            for dx, dy in directions:
                new_x, new_y = x + dx, y + dy
                new_angle = math.atan2(new_y, new_x)
                if (new_x, new_y) not in grid_map and angle_in_range(new_angle, min_angle, max_angle) and bound_condition(new_x, new_y, MAX_WIDTH):
                    valid_pos.append((new_x, new_y, new_angle - mid_angle(min_angle, max_angle)))
                
            sorted_new_pos = sorted(valid_pos, key=lambda x: (abs(x[2]), -x[2]))
            for new_x, new_y, _ in sorted_new_pos:
                queue.append((node.children[0], (new_x, new_y), min_angle, max_angle))
                break
        else:
            mid_angle_node = mid_angle(min_angle, max_angle)
            # 遍历子节点
            valid_poses = []
            for i, child in enumerate(node.children):
                valid_pos = []
                if i == 0:
                    min_child_angle = min_angle
                    max_child_angle = mid_angle_node
                else:
                    min_child_angle = mid_angle_node
                    max_child_angle = max_angle
               
                mid_child_angle = mid_angle(min_child_angle, max_child_angle)
                
                example_walk = []
                for dx, dy in directions:
                    new_x, new_y = x + dx, y + dy
                    new_angle = math.atan2(new_y, new_x)
                    if (new_x, new_y) not in grid_map and angle_in_range(new_angle, min_child_angle, max_child_angle) and bound_condition(new_x, new_y, MAX_WIDTH):
                        valid_pos.append((new_x, new_y, new_angle - mid_child_angle, min_child_angle, max_child_angle))
                        
                valid_poses.append(valid_pos)

            if all(len(valid_pos) for valid_pos in valid_poses):
                for child, valid_pos in zip(node.children, valid_poses):
                    sorted_new_pos = sorted(valid_pos, key=lambda x: (abs(x[2]), x[2], x[0]**2 + x[1]**2))
                    for new_x, new_y, _, min_child_angle, max_child_angle in sorted_new_pos:
                        queue.append((child, (new_x, new_y), min_child_angle, max_child_angle))
                        break
            else:
                valid_pos = []
                for dx, dy in directions:
                    new_x, new_y = x + dx, y + dy
                    new_angle = math.atan2(new_y, new_x)
                    if (new_x, new_y) not in grid_map and angle_in_range(new_angle, min_angle, max_angle) and bound_condition(new_x, new_y, MAX_WIDTH):
                        valid_pos.append((new_x, new_y, new_angle - mid_angle(min_angle, max_angle)))
                if len(valid_pos) == 0:
                    print(f'{node} terminated')
                    break
                sorted_new_pos = sorted(valid_pos, key=lambda x: (abs(x[2]), -x[2]))
                router = Node('S')
                node.insert_router(router)
                for new_x, new_y, _ in sorted_new_pos:
                    queue.append((router, (new_x, new_y), min_angle, max_angle))
                    break

    # 动态绘制图像
    fig, ax = plt.subplots(figsize=(8, 8))
    max_x = max(abs(x) for x, y, _ in plot_data)
    max_y = max(abs(y) for x, y, _ in plot_data)
    ax.set_xlim(-1.1 * max_x, 1.1 * max_x)
    ax.set_ylim(-1.1 * max_y, 1.1 * max_y)
    ax.grid(True)
    max_r = sqrt(max_x ** 2 + max_y ** 2)
    ax.set_aspect('equal', adjustable='box')
    def update(frame):
        ax.cla()  # 清除当前图像
        
        ax.set_xlim(-1.1 * max_x, 1.1 * max_x)
        ax.set_ylim(-1.1 * max_y, 1.1 * max_y)
        ax.grid(True)
        ax.set_aspect('equal', adjustable='box')

        # 绘制探索路径
        for (x, y, min_angle, max_angle) in explored_positions[frame:frame+1]:
            # 绘制角度区域
            angle_start = min_angle
            angle_end = max_angle
            angle_range = np.linspace(angle_start, angle_end, 30)
            for angle in angle_range:
                # 画扇形的边界
                ax.plot([0, 0 +  max_r * np.cos(angle)], [0, 0 + max_r * np.sin(angle)], c='gray', alpha=0.5)

            # 绘制当前节点
            ax.text(-1.1 * max_x, 1.1 * max_x, str(frame), fontsize=10, ha='center', va='center', color='white',
                    bbox=dict(facecolor='blue', edgecolor='none', boxstyle='round,pad=0.3'))
        
        # 绘制已发现的节点
        for (x, y, node) in plot_data[:frame]:
            ax.text(x, y, str(node.value), fontsize=10, ha='center', va='center', color='white',
                    bbox=dict(facecolor='blue', edgecolor='none', boxstyle='circle,pad=0.3'))

            if node.parent:
                px, py = node.parent.position
                ax.plot([x, px], [y, py], c='black')
        for (x, y, node) in plot_data[frame:frame+1]:
            ax.text(x, y, str(node.value), fontsize=10, ha='center', va='center', color='white',
                    bbox=dict(facecolor='red', edgecolor='none', boxstyle='circle,pad=0.3'))
            if node.parent:
                px, py = node.parent.position
                ax.plot([x, px], [y, py], c='black')

    # 创建动画
    ani = FuncAnimation(fig, update, frames=len(plot_data), interval=2000)

    # 保存为 GIF 动图
    ani.save('binary_tree_animation_with_exploration.mp4', writer='ffmpeg', fps=3)

    plt.close()
    return grid_map

def validate_mapping(root, grid_map):
    """
    检查映射的正确性。
    :param root: 二叉树的根节点
    :param grid_map: 格点映射的字典
    :return: 是否正确
    """
    visited = set()

    def dfs(node):
        if not node or node in visited:
            return True

        visited.add(node)
        x, y = node.position

        # 检查节点位置唯一性
        if grid_map.get((x, y)) != node:
            return False

        # 检查子节点连通性
        for child in [node.left, node.right]:
            if child:
                cx, cy = child.position
                if (abs(cx - x) + abs(cy - y)) != 1:  # 曼哈顿距离
                    return False

        return dfs(node.left) and dfs(node.right)

    return dfs(root)


def plot_binary_tree(root):
    """
    绘制生成的二叉树结构。
    :param root: 二叉树的根节点
    """
    def add_edges(node, edges, positions, x=0, y=0, dx=6):
        if not node:
            return
        positions[node] = (x, y)
        children_size = len(node.children)
        if children_size == 1:
            edges.append(((x, y), (x, y - 1)))
            add_edges(node.children[0], edges, positions, x, y - 1, dx)
        elif children_size == 2:
            edges.append(((x, y), (x - dx, y - 1)))
            add_edges(node.children[0], edges, positions, x - dx, y - 1, dx / 2)
            edges.append(((x, y), (x + dx, y - 1)))
            add_edges(node.children[1], edges, positions, x + dx, y - 1, dx / 2)
        else:
            return

    edges = []
    positions = {}
    add_edges(root, edges, positions)

    plt.figure(figsize=(8, 8))
    for (x1, y1), (x2, y2) in edges:
        plt.plot([x1, x2], [y1, y2], c='black')
    for node, (x, y) in positions.items():
        plt.scatter(x, y, c='blue')
        plt.text(x, y, str(node.value), fontsize=10, ha='center', va='center', color='white',
                 bbox=dict(facecolor='blue', edgecolor='none', boxstyle='circle,pad=0.3'))

    plt.gca().invert_yaxis()
    plt.grid(True)
    plt.show()
    
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


def is_complete_binary_tree(root):
    """
    检查二叉树是否是完全二叉树。
    :param root: 二叉树的根节点
    :return: 是否是完全二叉树
    """
    if not root:
        return True

    queue = deque([root])
    found_none = False

    while queue:
        node = queue.popleft()
        if node:
            if found_none:
                return False
            queue.append(node.left)
            queue.append(node.right)
        else:
            found_none = True

    return True


# 测试用例
levels = 4
root = build_complete_binary_tree(levels)
plot_binary_tree(root)
grid_map = map_binary_tree_to_grid(root)
plot_grid_map(grid_map,levels)

# plot_binary_tree(root)
# 验证映射正确性
# assert validate_mapping(root, grid_map), "映射验证失败！"
# print("映射验证成功！")

# # 检查二叉树是否是完全二叉树
# assert is_complete_binary_tree(root), "二叉树不是完全二叉树！"
# print("二叉树是完全二叉树！")