import numpy as np
from cpflow import *
import math
from tqdm import tqdm
from multiprocessing import Pool
from functools import partial

def reduce_gate_search(num_cp_gate,U):
    layer=[[0,1],[1,2]]
    decomposer = Synthesize(layer, target_unitary=U, label='cswap')
    options = StaticOptions(num_cp_gates=num_cp_gate, accepted_num_cz_gates=5, num_samples=100)
    success_results = decomposer.static(options,save_results=False)
    if len(success_results.decompositions) !=0:
        return U
    else:
        return np.identity(8)

def func(a):
    if a == '00':
        return [1,0]
    elif a == '01':
        return [0,1]
    elif a == '10':
        return [-1,0]
    else:
        return [0,-1] 

def gen_U(num,width):
    U=np.zeros((8,8))
    num = np.binary_repr(num,width=width)
    if num[1] != num[3] or num[5] != num[7]:
        return np.identity(8)
    else:
        U[0,0]=1
        U[2,2]=1
        U[4,4]=1
        U[5,6]=1
        for i in range(0,width,2):
            mat_num = func(num[i:i+2])
            if i==0:
                U[1,1]=mat_num[0]
                U[3,1]=mat_num[1]
            elif i==2:
                U[3,3]=mat_num[0]
                U[1,3]=mat_num[1]
            elif i==4:
                U[6,5]=mat_num[0]
                U[7,5]=mat_num[1]
            else:
                U[7,7]=mat_num[0]
                U[6,7]=mat_num[1]
    return U
            
if __name__=='__main__':
    result = []
    success=False
    for i in tqdm(range(256)):
        U = gen_U(i,width=8)
        if np.all(U == np.identity(8)):
            continue
        else:
            reduce_gate_search_U = partial(reduce_gate_search,U=U)
            with Pool(14) as p:
                success_result = p.map(reduce_gate_search_U,np.arange(5,33))
                for j,arr in enumerate(success_result):
                    if not np.all(arr == np.identity(8)):
                        result.append([arr,j+5])
                        success=True
                        break
            if success:
                break
    print(result)
    