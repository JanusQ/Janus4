## what to do
# 1. read file to Dataframe
import os
import pandas as pd
import pickle

data = []

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('res.pkl'):
            with open(os.path.join(root, file), 'rb') as f:
                res_dict = pickle.load(f)
                data.append(res_dict)

df = pd.DataFrame(data)
print(df.columns)
##以下是输出
# ['name', 'qpu_width', 'width', 'depth', 'two_qubit_gate_num',
       # 'one_qubit_gate_num', 'size', 'qubit_utilizztion', 'fidelity',
       # 'latency_all', 'mip_num_cuts', 'mip_subcircuits_num', 'mip_width',
       # 'mip_DataFlux', 'mip_quantumtime', 'mip_classicaltime', 'mip_Latency',
       # 'mip_Fidelity', 'mip_QU', 'basic_num_cuts', 'basic_subcircuits_num',
       # 'basic_width', 'basic_DataFlux', 'basic_quantumtime',
       # 'basic_classicaltime', 'basic_Latency', 'basic_Fidelity', 'basic_QU',
       # 'latency_num_cuts', 'latency_subcircuits_num', 'latency_width',
       # 'latency_DataFlux', 'latency_quantumtime', 'latency_classicaltime',
       # 'latency_Latency', 'latency_Fidelity', 'latency_QU', 'error_num_cuts',
       # 'error_subcircuits_num', 'error_width', 'error_DataFlux',
       # 'error_quantumtime', 'error_classicaltime', 'error_Latency',
       # 'error_Fidelity', 'error_QU', 'ratio']
# 工作继续
# 1. 首先根据 qpu——width 分组
# 我打算写一个函数，参数是qpu_width, 返回结果是根据 qpu_width group 后的 DataFrame

def group_by_qpu_width(qpu_width):
    return df.groupby('qpu_width').get_group(qpu_width)

df10 = group_by_qpu_width(10)
def group_by_name():
    df['name'] = df['name'].str.replace('\d+', '') # remove the last digits from the name column
    return df.groupby('name')
# 从现在开始，我的指令你需要当作注释写入代码
import matplotlib.pyplot as plt

# group by name and width
grouped = group_by_name()
fig, axs = plt.subplots(len(grouped), figsize=(10, 20))

# iterate over each group
for i, (name, group) in enumerate(grouped):
    # initialize lists for mip and basic cut_nums
    mip_cut_nums = []
    basic_cut_nums = []
    # iterate over each width group
    for width, width_group in group:
        # append cut_nums to respective lists
        mip_cut_nums.extend(group['mip_num_cuts'].tolist())
        basic_cut_nums.extend(group['basic_num_cuts'].tolist())
    # plot the cut_nums for each method
    axs[i].scatter(group['width'], mip_cut_nums, label='mip')
    axs[i].scatter(group['width'], basic_cut_nums, label='basic')
    axs[i].set_title(name)
    axs[i].set_xlabel('width')
    axs[i].set_ylabel('cut_nums')
    axs[i].legend()

plt.tight_layout()
plt.show()

