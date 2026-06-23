using Pkg

# 安装所需的包
Pkg.add("Distributed")
Pkg.add("BenchmarkTools") 
Pkg.add("HDF5")
Pkg.add("Plots")
Pkg.add("LinearAlgebra")
Pkg.add("SharedArrays")

using Base.Threads,Distributed,BenchmarkTools,HDF5,Plots
addprocs(180-nprocs()) #增加到16进程
@everywhere using LinearAlgebra,SharedArrays,Base.Threads

@everywhere const sqrt2_2 = sqrt(2)/2

@everywhere @kwdef struct Qram
    n::Int64
    classicalData::Vector{Int64}
    address::Vector{Int64}
    coefficient::Vector{Float64}
    k::Int64 = 1
    addressSize::Int64 = length(address)
    result::Matrix{Int64} = zeros(Int64,n+k,addressSize)
    process_array::Matrix{Int64} = zeros(Int64,2*(2^n-1),addressSize)
    sign_array::Matrix{Int64} = zeros(Int64,2,addressSize)
    entangled_qubit::Vector{Int64} = Vector{Int64}()
    position::Dict{Int64, Int64} = Dict{Int64, Int64}(i => 0 for i in 1:n+k)  #用于存储对应层数的比特目前到达的层数，当 i:i+1时，代表地址比特已经被成功加载
    activeQ::Vector{Int64} = zeros(Int64,2*(2^n-1))
end

#使用的是约化CSWAP门，即|111> -> -|111>，需要j1 = j2
@everywhere function swap_elements(mat::Matrix{Int64}, i1::Int64, j1::Int64, i2::Int64, j2::Int64)
    a = mat[i1,j1]
    b = mat[i2,j2]
    if a != 0 && b != 0
        if a == 3
            a = 4
        elseif a == 4
            a = 3
        elseif b == 3
            b = 4
        elseif b == 4
            b = 3
        end
    end
    mat[i1,j1] = b
    mat[i2,j2] = a
    if a == 1 && b == 1
        return true
    end
    return false
end

#使用的是两个CX门构成的约化swap,使用时需要让(i2,j2)的元素理想时为0
@everywhere function swap_elements_1(mat::Matrix{Int64}, i1::Int64, j1::Int64, i2::Int64, j2::Int64)
    a = mat[i1,j1]
    b = mat[i2,j2]
    t = false
    if b == 1
        if a == 4
            t = true
        elseif a == 1
            a = 0
        elseif a == 0
            a = 1
        end
    end
    mat[i1,j1] = b
    mat[i2,j2] = a
    return t
end

#使用的是两个CX门构成的约化swap,使用时需要让mat2的元素理想时为0
@everywhere function swap_elements_2(mat::Matrix{Int64},mat2::Matrix{Int64}, i1::Int64, j1::Int64, i2::Int64, j2::Int64)
    a = mat[i1,j1]
    b = mat2[i2,j2]
    t = false
    if b == 1
        if a == 4
            t = true
        elseif a == 1
            a = 0
        elseif a == 0
            a = 1
        end
    end
    mat[i1,j1] = b
    mat2[i2,j2] = a
    return t
end

@everywhere function tenToFour(num::Int64,len::Int64)
    string1 = reverse(join(digits(num,base = 4)))
    stop = len-length(string1)
    if stop >0
        for i = 1:stop
            string1 = "0" * string1
        end
    end
    return string1
end

@everywhere function genPauliDict(p::Float64,index;indexList::Vector{Int64}=[1,2,3])
    pauliDict = Dict{String,Float64}()
    if indexList == [1,2,3]
        if length(index) == 1
            indexList = filter!(x->x!=index,indexList)
            for i = 0 : 4^3-1
                string_index = tenToFour(i,3)
                t = false
                for x in indexList
                    if string_index[x] != '0'
                        t = true
                        break
                    end
                end
                if t
                    pauliDict[string_index] = 0.0
                else
                    if string_index[index] == '0'
                        pauliDict[string_index] = 1-p
                    else
                        pauliDict[string_index] = p/3
                    end
                end
            end
        else
            if index == [1,2]
                for i = 0:4^3-1
                    string_index = tenToFour(i,3)
                    t = false
                    if string_index[3] != '0'
                        t = true
                    end
                    if t
                        pauliDict[string_index] = 0.0
                    else
                        if string_index[1] == '0' && string_index[2] == '0'
                            pauliDict[string_index] = 1-p
                        else
                            pauliDict[string_index] = p/15
                        end
                    end
                end
            elseif index == [2,3]
                for i = 0:4^3-1
                    string_index = tenToFour(i,3)
                    t = false
                    if string_index[1] != '0'
                        t = true
                    end
                    if t
                        pauliDict[string_index] = 0.0
                    else
                        if string_index[3] == '0' && string_index[2] == '0'
                            pauliDict[string_index] = 1-p
                        else
                            pauliDict[string_index] = p/15
                        end
                    end
                end
            end
        end
    elseif indexList == [1,2]
        indexList = filter!(x->x!=index,indexList)
        if length(index)==1
            for i = 0 : 4^2-1
                string_index = tenToFour(i,2)
                t = false
                for x in indexList
                    if string_index[x] != '0'
                        t = true
                        break
                    end
                end
                if t
                    pauliDict[string_index] = 0.0
                else
                    if string_index[index] == '0'
                        pauliDict[string_index] = 1-p
                    else
                        pauliDict[string_index] = p/3
                    end
                end
            end
        else
            for i = 0 : 4^2-1
                string_index = tenToFour(i,2)
                if string_index != "00"
                    pauliDict[string_index] = p/15
                else
                    pauliDict[string_index] = 1-p
                end
            end
        end
    end
    return pauliDict
end

@everywhere function pauliStringSingleMutil(char1::Char,char2::Char)
    if char1 == char2
        return '0',1
    elseif char1 == '0'
        return char2,1
    elseif char2 == '0'
        return char1,1
    elseif (char1 == '1' && char2 == '2') || (char1 == '2' && char2 == '1')
        return '3',-1
    elseif (char1 == '1' && char2 == '3') || (char1 == '3' && char2 == '1')
        return '2',-1
    elseif (char1 == '2' && char2 == '3') || (char1 == '3' && char2 == '2')
        return '1',-1
    end
end

@everywhere function pauliStringMutil(str1::String,str2::String,value::Float64;mode::Int64=3)
    key = ""
    for i = 1:mode
        a,b = pauliStringSingleMutil(str1[i],str2[i])
        key *= a
        value *= b
    end
    return key,value
end

@everywhere function pauliDictMutil(dict1::Dict{String,Float64},dict2::Dict{String,Float64};mode::Int64=3)
    dict = Dict{String,Float64}(key => 0 for key in keys(dict1))
    for key in keys(dict1)
        for key2 in keys(dict2)
            a,b = pauliStringMutil(key,key2,dict1[key]*dict2[key2];mode)
            dict[a] += b
        end
    end
    return dict
end

#p均为两比特门错误率
@everywhere function genCswapDepolarizeError(p::Float64,p_single::Float64,p_idle_twoqgate::Float64)
    gate1 = pauliDictMutil(pauliDictMutil(genPauliDict(p_single,1),genPauliDict(p_single,2)),genPauliDict(p_single,3))
    gate2 = pauliDictMutil(genPauliDict(p_idle_twoqgate,1),genPauliDict(p,[2,3]))
    gate3 = pauliDictMutil(genPauliDict(p_idle_twoqgate,3),genPauliDict(p,[1,2]))
    a = pauliDictMutil(gate2,gate1)
    a = pauliDictMutil(gate1,a)
    a = pauliDictMutil(gate2,a)
    a = pauliDictMutil(gate1,a)
    a = pauliDictMutil(gate3,a)
    a = pauliDictMutil(gate1,a)
    a = pauliDictMutil(gate2,a)
    a = pauliDictMutil(gate1,a)
    a = pauliDictMutil(gate2,a)
    a = pauliDictMutil(gate1,a)
    return a
end

@everywhere function genLongIdentityError(p_idle_single::Float64,p_idle_twoqgate::Float64,layer::Int64)
    single_a = Dict{String,Float64}()
    single_a["0"] = 1-p_idle_single
    single_a["1"] = single_a["2"] = single_a["3"] = p_idle_single/3

    twoq_a = Dict{String,Float64}()
    twoq_a["0"] = 1-p_idle_twoqgate
    twoq_a["1"] = twoq_a["2"] = twoq_a["3"] = p_idle_twoqgate/3

    b = single_a
    maxIter = Int(div(layer-1,2)) ## twoq idle + oneq idle
    for _ = 1:maxIter
        b = pauliDictMutil(twoq_a,b;mode=1)
        b = pauliDictMutil(single_a,b;mode=1)
    end
    return b
end

@everywhere function genSwapError(p::Float64,layer::Int64)
    p_single = p/6
    I_single = pauliDictMutil(genPauliDict(p_single,1;indexList=[1,2]),genPauliDict(p_single,1;indexList=[1,2]);mode=2)
    cz = genPauliDict(p,[1,2];indexList = [1,2])
    swapError = pauliDictMutil(cz,I_single;mode=2)
    swapError = pauliDictMutil(I_single,swapError;mode=2)
    swapError = pauliDictMutil(cz,swapError;mode=2)
    swapError = pauliDictMutil(I_single,swapError;mode=2)
    for _ = 1:layer-5
        swapError = pauliDictMutil(I_single,swapError;mode=2)
    end
    return swapError
end

@everywhere function genCopyError(p::Float64)
    p_single = p/6
    p_idle_twoqgate = 1.75*p_single
    cz = genPauliDict(p,[1,2];indexList = [1,2])
    I_single = pauliDictMutil(genPauliDict(p_single,1;indexList=[1,2]),genPauliDict(p_single,1;indexList=[1,2]);mode=2)
    IdentityError = genLongIdentityError(p_single,p_idle_twoqgate,3)
    copyError = pauliDictMutil(I_single,pauliDictMutil(cz,I_single;mode=2);mode=2)
    return copyError,IdentityError,cz
end

@everywhere function qramInitial(n::Int64,classicalData::Vector{Int64},address::Vector{Int64},addressCoefficient::Vector{Float64})
    @assert length(classicalData) == 2^n "经典数据长度不符"
    @assert length(address) <= 2^n "地址个数超过n层Qram容量2^n"
    @assert length(address) > 0 "地址个数不能小于1"
    @assert length(address) == length(addressCoefficient) "地址系数的个数与地址个数不符"
    addressCoefficient = addressCoefficient/norm(addressCoefficient)
    return Qram(n = n, classicalData = classicalData, address = address, coefficient = addressCoefficient)
end

@everywhere function writeAddress(cir::Qram)
    for i = 1:cir.addressSize
        @assert (cir.address[i] >= 0 && cir.address[i] < 2^cir.n) "地址不合法"
        bit_string = string(cir.address[i],base=2,pad=cir.n)
        for j = 1:cir.n
            cir.result[j,i] = parse(Int,bit_string[j:j])
        end
    end
end

# 返回数字对应的二叉树坐标
@everywhere function numToCoord(t::Int64)
    p = Int(floor(log2(t+1)))
    return p,(t-2^p+1) ÷ 2 + 1
end

# 只对router里的数据比特适用,每一个router地址比特在前，数据比特在后
@everywhere function coordToNum(p::Int64,q::Int64)
    return 2^p - 2 + 2*q
end

@everywhere function routingLeft(cir::Qram,layer::Int64)
    for i = 2^layer-1:2:2^(layer+1)-2
        p,q = numToCoord(i)
        index = coordToNum(p+1,2*q-1)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 0
                t = swap_elements(cir.process_array,i+1,j,index,j)
                if t
                    cir.sign_array[1,j] *= -1
                end
            end
        end
        cir.activeQ[i] = cir.activeQ[i+1] = cir.activeQ[index] = 1
    end
end

@everywhere function routingLeftGate(cir::Qram,layer::Int64)
    applyQ = Vector{Vector{Int64}}()
    for i = 2^layer-1:2:2^(layer+1)-2
        p,q = numToCoord(i)
        index = coordToNum(p+1,2*q-1)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 0
                t = swap_elements(cir.process_array,i+1,j,index,j)
                if t
                    cir.sign_array[1,j] *= -1
                end
            end
        end
        cir.activeQ[i] = cir.activeQ[i+1] = cir.activeQ[index] = 1
        push!(applyQ,[i,i+1,index])
    end
    return applyQ
end

@everywhere function routingRight(cir::Qram,layer::Int64)
    for i = 2^layer-1:2:2^(layer+1)-2
        p,q = numToCoord(i)
        index = coordToNum(p+1,2*q)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 1
                t = swap_elements(cir.process_array,i+1,j,index,j)
                if t
                    cir.sign_array[1,j] *= -1
                end
            end
        end
        cir.activeQ[i] = cir.activeQ[i+1] = cir.activeQ[index] = 1
    end
end

@everywhere function routingRightGate(cir::Qram,layer::Int64)
    applyQ = Vector{Vector{Int64}}()
    for i = 2^layer-1:2:2^(layer+1)-2
        p,q = numToCoord(i)
        index = coordToNum(p+1,2*q)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 1
                t = swap_elements(cir.process_array,i+1,j,index,j)
                if t
                    cir.sign_array[1,j] *= -1
                end
            end
        end
        cir.activeQ[i] = cir.activeQ[i+1] = cir.activeQ[index] = 1
        push!(applyQ,[i,i+1,index])
    end
    return applyQ
end

@everywhere function routingLeftParaDown(cir::Qram,layer::Int64,label::Int64)
    n = cir.n
    k = cir.k
    t = false
    while layer >= 0 && label <= n + k 
        if layer > 0
            if layer < label
                routingLeft(cir,layer)
            elseif layer == label
                internalSwapDown(cir,label)
                cir.position[label] += 1
            end
            label += 1
            layer -= 2
            t = true
        elseif label <= cir.n
            addressBus(cir,label)
            layer -= 1
            t = true
            cir.position[label] += 1
        else
            dataBusInput(cir,label)
            layer -= 1
            t = true
            cir.position[label] += 1
        end
    end
    return t
end

@everywhere function routingLeftParaDownGate(cir::Qram,layer::Int64,label::Int64)
    n = cir.n
    k = cir.k
    CswapApplyQ = Vector{Vector{Int64}}()
    SwapApplyQ = Vector{Vector{Int64}}()
    BusOperaApplyQ = Vector{Vector{Int64}}()
    while layer >= 0 && label <= n + k 
        if layer > 0
            if layer < label
                a = routingLeftGate(cir,layer)
                append!(CswapApplyQ,a)
            elseif layer == label
                a = internalSwapDownGate(cir,label)
                cir.position[label] += 1
                append!(SwapApplyQ,a)
            end
            label += 1
            layer -= 2
        elseif label <= cir.n
            a = addressBusSwapDown(cir,label)
            layer -= 1
            cir.position[label] += 1
            append!(BusOperaApplyQ,a)
        else
            a = dataBusInputGate(cir,label)
            layer -= 1
            cir.position[label] += 1
            append!(BusOperaApplyQ,a)
        end
    end
    return CswapApplyQ,SwapApplyQ,BusOperaApplyQ
end

@everywhere function routingRightParaDown(cir::Qram,layer::Int64,label::Int64)
    n = cir.n
    k = cir.k
    t = false
    while layer > 0 && label <= n + k
        if layer < label
            routingRight(cir,layer)
            cir.position[label] += 1
            t = true
        end
        layer -= 2
        label += 1
    end
    return t
end

@everywhere function routingRightParaDownGate(cir::Qram,layer::Int64,label::Int64)
    n = cir.n
    k = cir.k
    CswapApplyQ = Vector{Vector{Int64}}()
    while layer > 0 && label <= n + k
        if layer < label
            a = routingRightGate(cir,layer)
            cir.position[label] += 1
            append!(CswapApplyQ,a)
        end
        layer -= 2
        label += 1
    end
    return CswapApplyQ
end

@everywhere function routingLeftParaUp(cir::Qram,layer::Int64,label::Int64)
    n=cir.n
    t = false
    while layer <= n && label >= layer 
        if layer > 0
            if layer < label
                routingLeft(cir,layer)
            elseif layer == label
                internalSwapUp(cir,label)
                cir.position[label] -= 1
            end
            label -= 1
            layer += 2
            t = true
        elseif label <= n
            addressBus(cir,label)
            cir.position[label] -= 1
            layer += 2
            label -= 1
            t = true
        else
            dataBusOutput(cir,label)
            cir.position[label] -= 1
            layer += 2
            label -= 1
            t = true
        end
    end
    return t
end

@everywhere function routingLeftParaUpGate(cir::Qram,layer::Int64,label::Int64)
    n=cir.n
    CswapApplyQ = Vector{Vector{Int64}}()
    SwapApplyQ = Vector{Vector{Int64}}()
    BusOperaApplyQ = Vector{Vector{Int64}}()
    while layer <= n && label >= layer 
        if layer > 0
            if layer < label
                a = routingLeftGate(cir,layer)
                append!(CswapApplyQ,a)
            elseif layer == label
                a = internalSwapUpGate(cir,label)
                cir.position[label] -= 1
                append!(SwapApplyQ,a)
            end
            label -= 1
            layer += 2
        elseif label <= n
            a = addressBusSwapUp(cir,label)
            cir.position[label] -= 1
            layer += 2
            label -= 1
            append!(BusOperaApplyQ,a)
        else
            a = dataBusOutputGate(cir,label)
            cir.position[label] -= 1
            layer += 2
            label -= 1
            append!(BusOperaApplyQ,a)
        end
    end
    return CswapApplyQ,SwapApplyQ,BusOperaApplyQ
end

@everywhere function routingRightParaUp(cir::Qram,layer::Int64,label::Int64)
    n = cir.n
    t = false
    while layer <= n && label > layer
        if layer > 0
            routingRight(cir,layer)
            cir.position[label] -= 1
            layer += 2
            label -= 1
            t = true
        else
            layer += 2
            label -= 1
        end
    end
    return t
end

@everywhere function routingRightParaUpGate(cir::Qram,layer::Int64,label::Int64)
    n = cir.n
    CswapApplyQ = Vector{Vector{Int64}}()
    while layer <= n && label > layer
        if layer > 0
            a = routingRightGate(cir,layer)
            cir.position[label] -= 1
            layer += 2
            label -= 1
            append!(CswapApplyQ,a)
        else
            layer += 2
            label -= 1
        end
    end
    return CswapApplyQ
end

@everywhere function internalSwapUp(cir::Qram,label::Int64)
    for j = 1:cir.addressSize
        for i = 2^label-1:2:2^(label+1)-2
            t = swap_elements_1(cir.process_array,i,j,i+1,j)
            if t
                cir.sign_array[1,j] *= -1
            end
            cir.activeQ[i] = 1
        end
    end
end

@everywhere function internalSwapDown(cir::Qram,label::Int64)
    for j = 1:cir.addressSize
        for i = 2^label-1:2:2^(label+1)-2
            t = swap_elements_1(cir.process_array,i+1,j,i,j)
            if t
                cir.sign_array[1,j] *= -1
            end
        end
    end
end

@everywhere function internalSwapUpGate(cir::Qram,label::Int64)
    applyQ = Vector{Vector{Int64}}()
    for j = 1:cir.addressSize
        for i = 2^label-1:2:2^(label+1)-2
            t = swap_elements_1(cir.process_array,i,j,i+1,j)
            if t
                cir.sign_array[1,j] *= -1
            end
            if j == 1
                push!(applyQ,[i,i+1])
            end
        end
    end
    return applyQ
end

@everywhere function internalSwapDownGate(cir::Qram,label::Int64)
    applyQ = Vector{Vector{Int64}}()
    for j = 1:cir.addressSize
        for i = 2^label-1:2:2^(label+1)-2
            t = swap_elements_1(cir.process_array,i+1,j,i,j)
            if t
                cir.sign_array[1,j] *= -1
            end
            if j == 1
                push!(applyQ,[i,i+1])
                cir.activeQ[i] = 1
            end
        end
    end
    return applyQ
end

@everywhere function addressBus(cir::Qram,label::Int64)
    for j = 1:cir.addressSize
        if cir.result[label,j] == 1
            cir.process_array[2,j] = (cir.process_array[2,j] + 1) % 2
        end
    end
    cir.activeQ[2] = 1
end

@everywhere function addressBusSwapDown(cir::Qram,label::Int64)
    applyQ = Vector{Vector{Int64}}()
    for j = 1:cir.addressSize
        t = swap_elements_2(cir.result,cir.process_array,label,j,2,j)
        if t
            cir.sign_array[1,j] *= -1
        end
        if j == 1
            push!(applyQ,[label,2])
        end
    end
    cir.activeQ[2] = 1
    return applyQ
end

@everywhere function addressBusSwapUp(cir::Qram,label::Int64)
    applyQ = Vector{Vector{Int64}}()
    for j = 1:cir.addressSize
        t = swap_elements_2(cir.process_array,cir.result,2,j,label,j)
        if t
            cir.sign_array[1,j] *= -1
        end
        if j == 1
            push!(applyQ,[label,2])
        end
    end
    return applyQ
end

@everywhere function dataBusInput(cir::Qram,label::Int64)
    for j = 1:cir.addressSize
        cir.result[label,j] = 3
        swap_elements_2(cir.result,cir.process_array,label,j,2,j)
    end
end

@everywhere function dataBusInputGate(cir::Qram,label::Int64)
    applyQ = Vector{Vector{Int64}}()
    for j = 1:cir.addressSize
        HGate(cir,label,j)
        t = swap_elements_2(cir.result,cir.process_array,label,j,2,j)
        if t
            cir.sign_array[1,j] *= -1
        end
        if j == 1
            push!(applyQ,[label,2])
        end
    end
    return applyQ
end

@everywhere function HGate(cir::Qram,index::Int64,index1::Int64)
    if cir.result[index,index1] == 3
        cir.result[index,index1] = 0
    elseif cir.result[index,index1] == 4
        cir.result[index,index1] = 1
    elseif cir.result[index,index1] == 1
        cir.result[index,index1] = 4
    else
        cir.result[index,index1] = 3
    end
end

@everywhere function dataBusOutput(cir::Qram,label::Int64)
    for j = 1:cir.addressSize
        swap_elements_2(cir.result,cir.process_array,label,j,2,j)
        HGate(cir,label,j)
    end
end

@everywhere function dataBusOutputGate(cir::Qram,label::Int64)
    applyQ = Vector{Vector{Int64}}()
    for j = 1:cir.addressSize
        t = swap_elements_2(cir.result,cir.process_array,label,j,2,j)
        HGate(cir,label,j)
        if t
            cir.sign_array[1,j] *= -1
        end
        if j == 1
            push!(applyQ,[label,2])
        end
    end
    return applyQ
end

@everywhere function dataCopyLeft(cir::Qram)
    for i = 2^cir.n-1:2:2^(cir.n+1)-2
        p,q = numToCoord(i)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 0 && cir.classicalData[2*q-1] == 1 && cir.process_array[i+1,j] == 3
                cir.process_array[i+1,j] = 4
            elseif cir.process_array[i,j] == 0 && cir.classicalData[2*q-1] == 1 && cir.process_array[i+1,j] == 4
                cir.process_array[i+1,j] = 3
            end
        end
    end
end

@everywhere function dataCopyLeftGate(cir::Qram)
    CopyApplyQ = Vector{Vector{Int64}}()
    for i = 2^cir.n-1:2:2^(cir.n+1)-2
        p,q = numToCoord(i)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 0 && cir.classicalData[2*q-1] == 1 && cir.process_array[i+1,j] == 3
                cir.process_array[i+1,j] = 4
            elseif cir.process_array[i,j] == 0 && cir.classicalData[2*q-1] == 1 && cir.process_array[i+1,j] == 4
                cir.process_array[i+1,j] = 3
            end
        end
        push!(CopyApplyQ,[i,i+1])
    end
    return CopyApplyQ
end

@everywhere function dataCopyRight(cir::Qram)
    for i = 2^cir.n-1:2:2^(cir.n+1)-2
        p,q = numToCoord(i)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 1 && cir.classicalData[2*q] == 1 && cir.process_array[i+1,j] == 3
                cir.process_array[i+1,j] = 4
            elseif cir.process_array[i,j] == 1 && cir.classicalData[2*q] == 1 && cir.process_array[i+1,j] == 4
                cir.process_array[i+1,j] = 3
            end
        end
    end
end

@everywhere function dataCopyRightGate(cir::Qram)
    CopyApplyQ = Vector{Vector{Int64}}()
    for i = 2^cir.n-1:2:2^(cir.n+1)-2
        p,q = numToCoord(i)
        for j = 1:cir.addressSize
            if cir.process_array[i,j] == 1 && cir.classicalData[2*q] == 1 && cir.process_array[i+1,j] == 3
                cir.process_array[i+1,j] = 4
            elseif cir.process_array[i,j] == 1 && cir.classicalData[2*q] == 1 && cir.process_array[i+1,j] == 4
                cir.process_array[i+1,j] = 3
            end
        end
        push!(CopyApplyQ,[i,i+1])
    end
    return CopyApplyQ
end

@everywhere function runQram(cir::Qram)
    writeAddress(cir)
    n = cir.n
    k = cir.k
    for i = 1:n
        start = cir.position[i]
        for j = start:i
            routingLeftParaDown(cir,j,i)
            routingRightParaDown(cir,j,i)
        end
    end
    label = n+k
    start = cir.position[label]
    for i = start:n-1
        routingLeftParaDown(cir,i,label)
        routingRightParaDown(cir,i,label)
    end
    dataCopyLeft(cir)
    dataCopyRight(cir)
    for i = n-1:-1:0
        routingLeftParaUp(cir,i,label)
        routingRightParaUp(cir,i,label)
    end
    for i = n:-1:1
        start = cir.position[i] - 1
        for j = start:-1:0
            routingLeftParaUp(cir,j,i)
            routingRightParaUp(cir,j,i)
        end
    end
end

@everywhere function changeComplex(cir::Qram,index::Int64)
    if cir.sign_array[2,index] == 0
        cir.sign_array[2,index] = 1
    else
        cir.sign_array[2,index] = 0
        cir.sign_array[1,index] = (cir.sign_array[1,index]+1)%2
    end
end

@everywhere function error_x_Single(cir::Qram,index::Int64)
    for j = 1 : cir.addressSize
        if cir.process_array[index,j] == 0
            cir.process_array[index,j] = 1
        elseif cir.process_array[index,j] == 1
            cir.process_array[index,j] = 0
        elseif cir.process_array[index,j] == 4
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
        end
    end
end

@everywhere function error_z_Single(cir::Qram,index::Int64)
    for j = 1 : cir.addressSize
        if cir.process_array[index,j] == 3
            cir.process_array[index,j] = 4
        elseif cir.process_array[index,j] == 4
            cir.process_array[index,j] = 3
        elseif cir.process_array[index,j] == 1
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
        end
    end
end

@everywhere function error_y_Single(cir::Qram,index::Int64)
    for j = 1 : cir.addressSize
        if cir.process_array[index,j] == 0
            cir.process_array[index,j] = 1
            changeComplex(cir,j)
        elseif cir.process_array[index,j] == 1
            cir.process_array[index,j] = 0
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
            changeComplex(cir,j)
        elseif cir.process_array[index,j] == 3
            cir.process_array[index,j] = 4
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
            changeComplex(cir,j)
        else
            cir.process_array[index,j] = 3
            changeComplex(cir,j)
        end
    end
end

@everywhere function error_x_Single_Bus(cir::Qram,index::Int64)
    for j = 1 : cir.addressSize
        if cir.result[index,j] == 0
            cir.result[index,j] = 1
        elseif cir.result[index,j] == 1
            cir.result[index,j] = 0
        elseif cir.result[index,j] == 4
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
        end
    end
end

@everywhere function error_z_Single_Bus(cir::Qram,index::Int64)
    for j = 1 : cir.addressSize
        if cir.result[index,j] == 3
            cir.result[index,j] = 4
        elseif cir.result[index,j] == 4
            cir.result[index,j] = 3
        elseif cir.result[index,j] == 1
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
        end
    end
end

@everywhere function error_y_Single_Bus(cir::Qram,index::Int64)
    for j = 1 : cir.addressSize
        if cir.result[index,j] == 0
            cir.result[index,j] = 1
            changeComplex(cir,j)
        elseif cir.result[index,j] == 1
            cir.result[index,j] = 0
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
            changeComplex(cir,j)
        elseif cir.result[index,j] == 3
            cir.result[index,j] = 4
            cir.sign_array[1,j] = (cir.sign_array[1,j]+1)%2
            changeComplex(cir,j)
        else
            cir.result[index,j] = 3
            changeComplex(cir,j)
        end
    end
end

@everywhere function errorTree(cir::Qram,noiseTreeArray::Matrix{Float64},opera::Bool)
    if opera == true
        for i = 1 : 2^(cir.n+1) -2 
            probability = rand()
            if probability <= noiseTreeArray[1,i]
                error_x_Single(cir,i)
            elseif probability <= noiseTreeArray[1,i] + noiseTreeArray[2,i]
                error_y_Single(cir,i)
            elseif probability <= noiseTreeArray[1,i] + noiseTreeArray[2,i] + noiseTreeArray[3,i]
                error_z_Single(cir,i)
            end
        end
    end
end

@everywhere function errorApplyStr(cir::Qram,index::Int64,char::Char)
    if char == '1'
        error_x_Single(cir,index)
    elseif char == '2'
        error_y_Single(cir,index)
    elseif char == '3'
        error_z_Single(cir,index)
    end
end

@everywhere function errorApplyStrBus(cir::Qram,index::Int64,char::Char)
    if char == '1'
        error_x_Single_Bus(cir,index)
    elseif char == '2'
        error_y_Single_Bus(cir,index)
    elseif char == '3'
        error_z_Single_Bus(cir,index)
    end
end

@everywhere function applyIdentityError(cir::Qram,IdentityError::Dict{String,Float64},applyErrorQ::Vector{Int64})
    if isempty(applyErrorQ)
        for i = 1 : 2^(cir.n+1) -2 
            if cir.activeQ[i] == 1
                probability = rand()
                s = 0.0
                opera = "0"
                for key in keys(IdentityError)
                    s += IdentityError[key]
                    if probability <= s
                        opera = key
                        break
                    end
                end
                errorApplyStr(cir,i,opera[1])
            end
        end
    else
        for i = 1 : 2^(cir.n+1) -2 
            if cir.activeQ[i] == 1 && ~(i in applyErrorQ)
                probability = rand()
                s = 0.0
                opera = "0"
                for key in keys(IdentityError)
                    s += IdentityError[key]
                    if probability <= s
                        opera = key
                        break
                    end
                end
                errorApplyStr(cir,i,opera[1])
            end
        end
    end
end

@everywhere function applyBusError(cir::Qram,IdentityError::Dict{String,Float64},SwapError::Dict{String,Float64},BusQ::Vector{Vector{Int64}})
    if isempty(BusQ)
        for i = 1 : cir.n+cir.k 
            probability = rand()
            s = 0.0
            opera = "0"
            for key in keys(IdentityError)
                s += IdentityError[key]
                if probability <= s
                    opera = key
                    break
                end
            end
            errorApplyStrBus(cir,i,opera[1])
        end
    else
        index = BusQ[1][1]
        applyDoubleQubitGateErrorBus(cir,SwapError,index)
        for i = 1 : cir.n+cir.k 
            if i != index
                probability = rand()
                s = 0.0
                opera = "0"
                for key in keys(IdentityError)
                    s += IdentityError[key]
                    if probability <= s
                        opera = key
                        break
                    end
                end
                errorApplyStrBus(cir,i,opera[1])
            end
        end
    end
end

@everywhere function applyCswapError(cir::Qram,CswapError::Dict{String,Float64},CswapQ::Vector{Vector{Int64}},applyErrorQ::Vector{Int64})
    for x in CswapQ
        applyErrorQ = vcat(applyErrorQ,x)
        probability = rand()
        s = 0.0
        opera = "000"
        for key in keys(CswapError)
            s += CswapError[key]
            if probability <= s
                opera = key
                break
            end
        end
        for i = 1:3
            errorApplyStr(cir,x[i],opera[i])
        end
    end
    return applyErrorQ
end

@everywhere function applyDoubleQubitGateError(cir::Qram,Error::Dict{String,Float64},applyQ::Vector{Vector{Int64}},applyErrorQ::Vector{Int64})
    for x in applyQ
        applyErrorQ = vcat(applyErrorQ,x)
        probability = rand()
        s = 0.0
        opera = "00"
        for key in keys(Error)
            s += Error[key]
            if probability <= s
                opera = key
                break
            end
        end
        for i = 1:2
            errorApplyStr(cir,x[i],opera[i])
        end
    end
    return applyErrorQ
end

@everywhere function applyDoubleQubitGateErrorBus(cir::Qram,Error::Dict{String,Float64},index::Int64)
    probability = rand()
    s = 0.0
    opera = "00"
    for key in keys(Error)
        s += Error[key]
        if probability <= s
            opera = key
            break
        end
    end
    errorApplyStr(cir,2,opera[2])
    errorApplyStrBus(cir,index,opera[1])
end

@everywhere function errorTreeGate(cir::Qram,CswapQ::Vector{Vector{Int64}},SwapQ::Vector{Vector{Int64}},BusQ::Vector{Vector{Int64}},
                                singleIdentityError::Dict{String,Float64},swapError::Dict{String,Float64},
                                MiddleIdentityError::Dict{String,Float64},LongIdentityError::Dict{String,Float64},
                                longSwapError::Dict{String,Float64},CswapError::Dict{String,Float64})
    applyErrorQ=Vector{Int64}() #只用来记录Tree上被施加了错误的比特
    if isempty(BusQ)
        if isempty(CswapQ) && isempty(SwapQ)
            applyIdentityError(cir,singleIdentityError,applyErrorQ)
        elseif isempty(CswapQ) && ~isempty(SwapQ)
            applyErrorQ = applyDoubleQubitGateError(cir,swapError,SwapQ,applyErrorQ)
            applyIdentityError(cir,MiddleIdentityError,applyErrorQ)
        elseif isempty(SwapQ) && ~isempty(CswapQ)
            applyErrorQ = applyCswapError(cir,CswapError,CswapQ,applyErrorQ)
            applyIdentityError(cir,LongIdentityError,applyErrorQ)
        else
            applyErrorQ = applyDoubleQubitGateError(cir,longSwapError,SwapQ,applyErrorQ)
            applyErrorQ = applyCswapError(cir,CswapError,CswapQ,applyErrorQ)
            applyIdentityError(cir,LongIdentityError,applyErrorQ)
        end
    else
        if isempty(CswapQ) && isempty(SwapQ)
            applyBusError(cir,MiddleIdentityError,swapError,BusQ)
            push!(applyErrorQ,2)
            applyIdentityError(cir,MiddleIdentityError,applyErrorQ)
        elseif isempty(CswapQ) && ~isempty(SwapQ)
            applyBusError(cir,MiddleIdentityError,swapError,BusQ)
            push!(applyErrorQ,2)
            applyErrorQ = applyDoubleQubitGateError(cir,swapError,SwapQ,applyErrorQ)
            applyIdentityError(cir,MiddleIdentityError,applyErrorQ)
        elseif isempty(SwapQ) && ~isempty(CswapQ)
            applyBusError(cir,LongIdentityError,longSwapError,BusQ)
            push!(applyErrorQ,2)
            applyErrorQ = applyCswapError(cir,CswapError,CswapQ,applyErrorQ)
            applyIdentityError(cir,LongIdentityError,applyErrorQ)
        else
            applyBusError(cir,LongIdentityError,longSwapError,BusQ)
            push!(applyErrorQ,2)
            applyErrorQ = applyDoubleQubitGateError(cir,longSwapError,SwapQ,applyErrorQ)
            applyErrorQ = applyCswapError(cir,CswapError,CswapQ,applyErrorQ)
            applyIdentityError(cir,LongIdentityError,applyErrorQ)
        end
    end
end

@everywhere function errorTreeDataCopy(cir::Qram,gateError1::Dict{String,Float64},gateError2::Dict{String,Float64},applyQ::Vector{Vector{Int64}})
    applyErrorQ = Vector{Int64}()
    applyErrorQ = applyDoubleQubitGateError(cir,gateError1,applyQ,applyErrorQ)
    applyIdentityError(cir,gateError2,applyErrorQ)  
    applyBusError(cir,gateError2,gateError1,Vector{Vector{Int64}}())
end

@everywhere function composeCoefficient(singleVector::Vector{Int64})::ComplexF64
    if singleVector[1] == 0 && singleVector[1] == 0
        return 1+0im
    elseif singleVector[1] == 0 && singleVector[1] == 1
        return 1im
    elseif singleVector[1] == 1 && singleVector[1] == 0
        return -1+0im
    else
        return -1im
    end
end

@everywhere function composeVector(singleVector::Vector{Int64},n::Int64,k::Int64)
    vector1 = zeros(ComplexF64,2^n)
    vector1[parse(Int64,join(singleVector[1:n]),base=2)+1] = 1.0+0im
    for i = n+1:n+k
        if singleVector[i] == 0
            vector1 = kron(vector1,[1.0+0im,0.0+0.0im])
        elseif singleVector[i] == 1
            vector1 = kron(vector1,[0.0+0.0im,1.0+0.0im])
        elseif singleVector[i] == 3
            vector1 = kron(vector1,[sqrt2_2+0.0im,sqrt2_2+0.0im])
        else
            vector1 = kron(vector1,[sqrt2_2+0.0im,-sqrt2_2+0.0im])
        end
    end
    return vector1
end

@everywhere function composeMatrix(vector1::Vector{Int64},vector2::Vector{Int64},n::Int64,k::Int64)::Matrix{ComplexF64}
    return composeVector(vector1,n,k)*composeVector(vector2,n,k)'
end

@everywhere function stringInner(vector1::Vector{Int64},vector2::Vector{Int64},entangledQubitVector::Vector{Int64})::Float64
    factor=1.0
    for i in entangledQubitVector
        if ((vector1[i]==3 && vector2[i]==1) || (vector1[i]==3 && vector2[i]==0) || (vector1[i]==4 && vector2[i]==0) ||
            (vector1[i]==1 && vector2[i]==3) || (vector1[i]==0 && vector2[i]==3) || (vector1[i]==0 && vector2[i]==4))
            factor=factor*sqrt2_2
        elseif (vector1[i]==4 && vector2[i]==1) || (vector1[i]==1 && vector2[i]==4)
            factor=-factor*sqrt2_2
        elseif vector2[i] != vector1[i]
            factor = 0.0
            break
        end
    end
    return factor
end

@everywhere function stringInnerResult(vector1::Vector{Int64},vector2::Vector{Int64},n::Int64,k::Int64)
    factor::Float64 = 1.0
    for i = 1:n+k
        if vector2[i] == 3 || (vector2[i] == 4 && vector1[i] == 0)
            factor = factor * sqrt2_2
        elseif vector2[i] == 4 && vector1[i] == 1
            factor = -factor * sqrt2_2
        elseif vector2[i] != vector1[i]
            factor = 0.0
            break
        end
    end
    return factor
end

@everywhere function seekEntangledQubit(cir::Qram)
    for i = 1 : 2^(cir.n+1)-2
        for j = 1:cir.addressSize-1
            if cir.process_array[i,j] != cir.process_array[i,j+1]
                push!(cir.entangled_qubit,i)
                break
            end
        end
    end
end

@everywhere function runQramWithNoise(cir::Qram,noiseTreeArray::Matrix{Float64})
    writeAddress(cir)
    n = cir.n
    k = cir.k
    for i = 1:n
        start = cir.position[i]
        for j = start:i
            t = routingLeftParaDown(cir,j,i)
            errorTree(cir,noiseTreeArray,t)
            t = routingRightParaDown(cir,j,i)
            errorTree(cir,noiseTreeArray,t)
        end
    end
    label = n+k
    start = cir.position[label]
    for i = start:n-1
        t = routingLeftParaDown(cir,i,label)
        errorTree(cir,noiseTreeArray,t)
        t = routingRightParaDown(cir,i,label)
        errorTree(cir,noiseTreeArray,t)
    end
    dataCopyLeft(cir)
    errorTree(cir,noiseTreeArray,true)
    dataCopyRight(cir)
    errorTree(cir,noiseTreeArray,true)
    for i = n-1:-1:0
        t = routingLeftParaUp(cir,i,label)
        errorTree(cir,noiseTreeArray,t)
        t = routingRightParaUp(cir,i,label)
        errorTree(cir,noiseTreeArray,t)
    end
    for i = n:-1:1
        start = cir.position[i] - 1
        for j = start:-1:0
            t = routingLeftParaUp(cir,j,i)
            errorTree(cir,noiseTreeArray,t)
            t = routingRightParaUp(cir,j,i)
            errorTree(cir,noiseTreeArray,t)
        end
    end
end
#p均为两比特门错误率，单比特门错误率为p/10
@everywhere function runQramWithGateNoise(cir::Qram,
    singleIdentityError::Dict{String,Float64},
    swapError::Dict{String,Float64},
    MiddleIdentityError::Dict{String,Float64},
    LongIdentityError::Dict{String,Float64},
    longSwapError::Dict{String,Float64},
    CswapError::Dict{String,Float64},
    CopyLeftError::Dict{String,Float64},
    CopyLeftIdentityError::Dict{String,Float64},
    cz::Dict{String,Float64})

    writeAddress(cir)
    n = cir.n
    k = cir.k
    emptyVector = Vector{Vector{Int64}}()
    for i = 1:n
        start = cir.position[i]
        for j = start:i
            a,b,c = routingLeftParaDownGate(cir,j,i)
            errorTreeGate(cir,a,b,c,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
            a = routingRightParaDownGate(cir,j,i)
            errorTreeGate(cir,a,emptyVector,emptyVector,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
        end
    end
    label = n+k
    start = cir.position[label]
    for i = start:n-1
        a,b,c = routingLeftParaDownGate(cir,i,label)
        errorTreeGate(cir,a,b,c,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
        a = routingRightParaDownGate(cir,i,label)
        errorTreeGate(cir,a,emptyVector,emptyVector,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
    end
    a = dataCopyLeftGate(cir)
    errorTreeDataCopy(cir,CopyLeftError,CopyLeftIdentityError,a)
    a = dataCopyRightGate(cir)
    errorTreeDataCopy(cir,cz,singleIdentityError,a)
    for i = n-1:-1:0
        a,b,c = routingLeftParaUpGate(cir,i,label)
        errorTreeGate(cir,a,b,c,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
        a = routingRightParaUpGate(cir,i,label)
        errorTreeGate(cir,a,emptyVector,emptyVector,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
    end
    for i = n:-1:1
        start = cir.position[i] - 1
        for j = start:-1:0
            a,b,c = routingLeftParaUpGate(cir,j,i)
            errorTreeGate(cir,a,b,c,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
            a = routingRightParaUpGate(cir,j,i)
            errorTreeGate(cir,a,emptyVector,emptyVector,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError)
        end
    end
end

@everywhere function genIdealResult(address::Vector{Int64},classicalData::Vector{Int64},addressSize::Int64,n::Int64)
    idealResult = Matrix{Int64}(undef,n+1,addressSize)
    for j = 1:addressSize
        bit_string = string(address[j],base=2,pad=n)
        for i = 1:n
            idealResult[i,j] = parse(Int,bit_string[i:i])
        end
        idealResult[n+1,j] = classicalData[address[j]+1]
    end
    return idealResult
end

@everywhere function genIdealVector(address::Vector{Int64},classicalData::Vector{Int64},addressSize::Int64,n::Int64,addressCoefficient::Vector{Float64})
    idealVector = zeros(Float64,2^(n+1))
    for j = 1:addressSize
        index = address[j]
        idealVector[2*index+classicalData[index+1]+1] = addressCoefficient[j]
    end
    return idealVector
end

@everywhere function calculateFidelityPure(cir::Qram)
    idealResult = genIdealResult(cir.address,cir.classicalData,cir.addressSize,cir.n)
    fidelity::ComplexF64 = 0.0 + 0.0im
    n = cir.n
    k = cir.k
    for j = 1:cir.addressSize
        for jj = 1:cir.addressSize
            factor = stringInnerResult(idealResult[:,j],cir.result[:,jj],n,k)
            if factor != 0
                if cir.sign_array[1,jj]==0 && cir.sign_array[2,jj]==0
                    fidelity=fidelity+factor*cir.coefficient[j]*cir.coefficient[jj]
                elseif cir.sign_array[1,jj]==1 && cir.sign_array[2,jj]==0
                    fidelity=fidelity-factor*cir.coefficient[j]*cir.coefficient[jj]
                elseif cir.sign_array[1,jj]==0 && cir.sign_array[2,jj]==1
                    fidelity=fidelity+1im*factor*cir.coefficient[j]*cir.coefficient[jj]
                else
                    fidelity=fidelity-1im*factor*cir.coefficient[j]*cir.coefficient[jj]
                end
            end
        end
    end
    return abs(fidelity)^2
end

@everywhere function calculateFidelityMixed(cir::Qram)
    n = cir.n
    k = cir.k
    densityMatrix = zeros(ComplexF64,2^(n+k),2^(n+k))
    idealVector = genIdealVector(cir.address,cir.classicalData,cir.addressSize,cir.n,cir.coefficient)
    addressSize = cir.addressSize
    for j = 1:addressSize
        densityMatrix .= densityMatrix .+ composeMatrix(cir.result[:,j],cir.result[:,j],n,k) .* (cir.coefficient[j]^2 * abs(composeCoefficient(cir.sign_array[:,j]))^2)
    end
    coefficient = complex.(cir.coefficient)
    lock_obj = ReentrantLock()
    @threads for j = 1:addressSize-1
        for jj = j+1:addressSize
            factor = complex(stringInner(cir.process_array[:,j],cir.process_array[:,jj],cir.entangled_qubit))
            if factor != 0.0
                factor = coefficient[j] * coefficient[jj] * composeCoefficient(cir.sign_array[:,j]) * composeCoefficient(cir.sign_array[:,jj])' * factor
                arr = composeMatrix(cir.result[:,j],cir.result[:,jj],n,k) .* factor
                lock(lock_obj) do
                    densityMatrix .+= arr .+ arr'
                end
            end
        end
    end
    return abs(dot(idealVector,densityMatrix,idealVector))
end
#用于Bus没有噪声的情况
@everywhere function calculateFidelityMixedFast(cir::Qram)
    n = cir.n
    k = cir.k
    addressSize = cir.addressSize
    idealResult = genIdealResult(cir.address,cir.classicalData,cir.addressSize,cir.n)
    fidelity::ComplexF64 = 0.0 + 0.0im
    coefficient = complex.(cir.coefficient)
    lock_obj = ReentrantLock()
    @threads for j = 1:addressSize
        for jj = j : addressSize
            if jj != j
                factor = complex(stringInner(cir.process_array[:,j],cir.process_array[:,jj],cir.entangled_qubit))
                if factor != 0
                    factor *= stringInnerResult(idealResult[:,j],cir.result[:,j],n,k) * stringInnerResult(idealResult[:,jj],cir.result[:,jj],n,k) *
                                coefficient[j]^2 * coefficient[jj]^2 * composeCoefficient(cir.sign_array[:,j]) * composeCoefficient(cir.sign_array[:,jj])'
                    lock(lock_obj) do
                        fidelity += (factor+factor')
                    end
                end  
            else
                lock(lock_obj) do
                    fidelity += (stringInnerResult(idealResult[:,j],cir.result[:,j],n,k)^2 * coefficient[j]^4 * abs(composeCoefficient(cir.sign_array[:,j]))^2)
                end
            end
        end
    end
    return abs(fidelity)
end

#用于Bus有噪声的情况
@everywhere function calculateFidelityMixedFast2(cir::Qram)
    let
        n = cir.n
        k = cir.k
        addressSize = cir.addressSize
        idealResult = genIdealResult(cir.address, cir.classicalData, cir.addressSize, cir.n)
        coefficient = complex.(cir.coefficient)
        entangled_qubit = cir.entangled_qubit
        composed_coeffs = [composeCoefficient(cir.sign_array[:,j]) for j in 1:addressSize]
        
        stringInnerArray = Array{ComplexF64}(undef, addressSize, addressSize)
        for j in 1:addressSize
            for jj in j:addressSize
                stringInnerArray[j, jj] = complex(stringInner(cir.process_array[:,j], cir.process_array[:,jj], entangled_qubit))
                if j != jj
                    stringInnerArray[jj, j] = stringInnerArray[j, jj]
                end
            end
        end

        stringInnerResultArray = Array{ComplexF64}(undef, addressSize, addressSize)
        for j in 1:addressSize
            for jj in 1:addressSize
                stringInnerResultArray[j, jj] = complex(stringInnerResult(idealResult[:,j], cir.result[:,jj], n, k))
            end
        end

        local_fids = zeros(ComplexF64, Threads.nthreads())
        
        tasks = Vector{Task}(undef, Threads.nthreads())
        chunk_size = cld(addressSize, Threads.nthreads())
        
        for tid in 1:Threads.nthreads()
            start_idx = (tid-1) * chunk_size + 1
            end_idx = min(tid * chunk_size, addressSize)
            
            local start_j = start_idx
            local end_j = end_idx

            tasks[tid] = Threads.@spawn begin
                for j in start_j:end_j
                    # 相同索引计算 (j == jj 情况)
                    coeff_j_squared = coefficient[j]^2
                    composed_j_squared = abs(composed_coeffs[j])^2
                    
                    for jjj in 1:addressSize
                        # inner_jjj = stringInnerResult(idealResult[:,jjj], cir.result[:,j], n, k)
                        inner_jjj = stringInnerResultArray[jjj,j]
                        coeff_jjj = coefficient[jjj]
                        if inner_jjj != 0
                            for jjjj in 1:addressSize
                                # inner_jjjj = stringInnerResult(idealResult[:,jjjj], cir.result[:,j], n, k)
                                inner_jjjj = stringInnerResultArray[jjjj,j]
                                if inner_jjjj != 0
                                    local_fids[Threads.threadid()] += inner_jjj * inner_jjjj * 
                                                                    coeff_j_squared * coeff_jjj * 
                                                                    coefficient[jjjj] * composed_j_squared
                                end
                            end
                        end
                    end
                    
                    # 不同索引计算 (j != jj 情况)
                    for jj = (j+1):addressSize
                        # factor = complex(stringInner(cir.process_array[:,j], cir.process_array[:,jj], cir.entangled_qubit))
                        factor = stringInnerArray[j,jj]
                        if factor != 0
                            coeff_j = coefficient[j]
                            coeff_jj = coefficient[jj]
                            composed_j = composed_coeffs[j]
                            composed_jj_conj = conj(composed_coeffs[jj])
                            
                            for jjj in 1:addressSize
                                # inner_j_jjj = stringInnerResult(idealResult[:,jjj], cir.result[:,j], n, k)
                                inner_j_jjj = stringInnerResultArray[jjj,j]
                                coeff_jjj = coefficient[jjj]
                                if inner_j_jjj != 0
                                    for jjjj in 1:addressSize
                                        # inner_jj_jjjj = stringInnerResult(idealResult[:,jjjj], cir.result[:,jj], n, k)
                                        inner_jj_jjjj = stringInnerResultArray[jjjj,jj]
                                        if inner_jj_jjjj != 0
                                            term = factor * inner_j_jjj * inner_jj_jjjj * 
                                                coeff_j * coeff_jj * coeff_jjj * coefficient[jjjj] * 
                                                composed_j * composed_jj_conj
                                            
                                            local_fids[Threads.threadid()] += (term + conj(term))
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
        
        # 等待所有任务完成
        for task in tasks
            wait(task)
        end
        # 汇总所有线程的结果
        fidelity = sum(local_fids)
        return abs(fidelity)
    end
end

@everywhere function calculate_expected_ones(cir::Qram)
    num_bits, num_states = size(cir.process_array)
    
    probabilities = abs2.(cir.coefficient)
    
    expected_ones = zeros(Float64, num_bits)

    for bit_idx in 1:num_bits
        for state_idx in 1:num_states
            if cir.process_array[bit_idx, state_idx] == 1
                expected_ones[bit_idx] += probabilities[state_idx]
            elseif cir.process_array[bit_idx, state_idx] == 3 || cir.process_array[bit_idx, state_idx] == 4
                expected_ones[bit_idx] += probabilities[state_idx]/2
            end
        end
    end
    return expected_ones
end

@everywhere function judgeZero(cir::Qram,startIndex::Int64,stopIndex::Int64)
    t = 1.0
    for i = startIndex:stopIndex
        if i in cir.entangled_qubit
            t = 0.0
            break
        else
            if cir.process_array[i,1] != 0
                t = 0.0
                break
            end
        end
    end
    return t
end


function getFidelityGate(n::Int64,classicalData::Vector{Int64},address::Vector{Int64},addressCoefficient::Vector{Float64},p::Float64,shot::Int64)
    fidelityArray = SharedArray(Vector{Float64}(undef,shot))
    p_single = p/6
    p_idle_twoqgate = 1.75*p_single
    # two qubit gate idle error = two qubit gate lantency(35ns)/ single qubit gate latency(20ns) * single qubit gate idle error
    CswapError = genCswapDepolarizeError(p,p_single,p_idle_twoqgate)
    singleIdentityError = genLongIdentityError(p_single,p_idle_twoqgate,1)
    MiddleIdentityError = genLongIdentityError(p_single,p_idle_twoqgate,5)
    LongIdentityError = genLongIdentityError(p_single,p_idle_twoqgate,11)
    swapError = genSwapError(p,5)
    longSwapError = genSwapError(p,11)
    CopyLeftError,CopyLeftIdentityError,cz = genCopyError(p)
    @sync @distributed for i = 1:shot
        a = qramInitial(n,classicalData,address,addressCoefficient)
        runQramWithGateNoise(a,singleIdentityError,swapError,MiddleIdentityError,LongIdentityError,longSwapError,CswapError,CopyLeftError,CopyLeftIdentityError,cz)
        seekEntangledQubit(a)
        if length(a.entangled_qubit) == 0
            fidelityArray[i] = calculateFidelityPure(a)
        else
            fidelityArray[i] = calculateFidelityMixedFast2(a)
        end
    end
    return sum(fidelityArray)/shot, fidelityArray
end

function fidelityChange(fidelityArray::Vector{Float64},shots::Int64)
    fidelityChangeArray = Vector{Float64}(undef,shots)
    sum = 0.0
    for i = 1 : shots
        sum += fidelityArray[i]
        fidelityChangeArray[i] = sum/i
    end
    return fidelityChangeArray
end

function sampleQramGate(n::Int64, shots::Int64, classicalData::Vector{Int64}, address::Vector{Int64}, addressCoefficient::Vector{Float64}, p::Float64, filepath; savePicture=true, saveH5=true)
    averageFidelity, fidelityArray = getFidelityGate(n, classicalData, address, addressCoefficient, p, shots)
    open(joinpath(filepath, "results.csv"), "a") do io
        write(io, "$n,$p,$shots,$averageFidelity\n")
    end
    fidelityArray = collect(fidelityArray)
    fidelityChangeArray = fidelityChange(fidelityArray,shots)
    n_samples = 1:shots
    ## plot the fidelity change array with gap 10
    if shots > 1e7
        gap = 100
    else
        gap = 10
    end
    n_samples_gap = gap:gap:shots
    fidelityChangeArray_gap = fidelityChangeArray[n_samples_gap]
    plot(n_samples_gap, fidelityChangeArray_gap,
    label="$n-layer",          # 图例标签
    xlabel="Number of Samples",  # x轴标签
    ylabel="Fidelity",           # y轴标签
    title="Fidelity vs Sampling",  # 图表标题
    linewidth=2,                 # 线条粗细
    color=:blue,                 # 线条颜色
    markersize=3,                # 标记大小
    grid=true,                   # 显示网格
    )
    filename = "$(n)_layer_gate_fidelity_fullAddress_twoqgate_$(p)_error_$(shots)_shots.png"
    filename = joinpath(filepath,filename)
    if savePicture
        savefig(filename)
    end
    GC.gc()  # Force garbage collection
end

function sampleQramGateP(n::Int64, shots::Int64, classicalData::Vector{Int64}, address::Vector{Int64}, addressCoefficient::Vector{Float64}, p::Float64, filepath; savePicture=true, saveH5=true)
    averageFidelity, fidelityArray = getFidelityGate(n, classicalData, address, addressCoefficient, p, shots)
    open(joinpath(filepath, "results.csv"), "a") do io
        write(io, "$n,$p,$shots,$averageFidelity\n")
    end
    GC.gc()  # Force garbage collection
end

##[1e-8,5e-8,1e-7,5e-7,1e-6,5e-6,1e-5,5e-5,1e-4,5e-4,1e-3,0.0038,5e-3,1e-2]
##1e-2,5e-3,0.0038,1e-3,5e-4,1e-4,5e-5,1e-5,5e-6,1e-6,5e-7,1e-7,5e-8,1e-8


# -------------------------------------------------------------
# 1. 定义常量和范围
# -------------------------------------------------------------
P_VALUES = [1e-2,5e-3,0.0038,1e-3,5e-4,1e-4,5e-5,1e-5,5e-6,1e-6,5e-7,1e-7]
# 请根据您的需求修改 N 的范围。这里假设您想让 N 从 5 跑到 10。
N_RANGE = 8:8

# -------------------------------------------------------------
# 2. 将核心定义同步到所有 Worker 进程
# -------------------------------------------------------------
@everywhere begin
    # 确保所有 worker 知道路径常量
    full_path_base = "qramRes8layer/"
    # 确保所有 worker 都能访问到 sampleQramGate 函数的定义和相关的模块
    # 如果您的函数在某个模块中，请使用: @everywhere using YourModule 
    
    # 文件夹创建：只在主进程 (Worker ID 1) 上执行
    if myid() == 1
        if !ispath(full_path_base)
            mkdir(full_path_base)
            println("文件夹已创建：", full_path_base)
        else
            println("文件夹已存在：", full_path_base)
        end
    end
end
# 主进程等待 worker 启动和设置完成
# (在 @distributed for 之前无需显式同步，循环会自动等待)


# -------------------------------------------------------------
# 3. 创建所有 (p, n) 任务组合
# -------------------------------------------------------------
TASKS = [(p, n) for p in P_VALUES for n in N_RANGE]

println("总共有 $(length(TASKS)) 个任务将被并行执行...")

# -------------------------------------------------------------
# 4. 使用 @distributed for 并行化所有任务
# -------------------------------------------------------------
# @distributed 自动将 TASKS 中的元素分发给不同的 worker 进程
for (p, n) in TASKS
    full_path = full_path_base

    if p >1e-5
        shots = 1e5
    elseif p >1e-6
        shots = 5e5
    elseif p> 1e-7
        shots = 5e6
    elseif p>= 1e-8
        shots = 1e7
    else
        shots = 1e7
    end
    classicalData = ones(Int,2^n)
    address = [i for i = 0:2^n-1]
    addressCoefficient = ones(Float64,2^n)
    @time sampleQramGate(n,Int(shots),classicalData,address,addressCoefficient,p,full_path;saveH5=true,savePicture=true)
    GC.gc()
end


# 循环结束后，清理所有 worker 进程的内存
@everywhere GC.gc()
