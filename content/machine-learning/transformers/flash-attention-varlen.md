---
title: "Flash Attention 与变长序列优化"
date: 2026-03-05
tags:
  - Flash Attention
  - Transformer
  - GPU优化
lang: zh
english: machine-learning/transformers/flash-attention-varlen.en
---

> 🌐 [Read in English](./flash-attention-varlen.en.md)

## 核心概念

Flash Attention 是一种 IO-Aware 的 Self-Attention 实现，通过 **kernel fusion + tiling** 把整个 $QK^TV$ 计算压缩进一个 GPU kernel，避免反复读写 HBM，从而在不损失精度的前提下大幅加速。

算法演进全景：

![Flash Attention 算法演进](./assets/flash-attention-overview.jpeg)

---

## 为什么标准 Attention 慢

标准实现分三步，每一步都是一个独立的 CUDA kernel，中间结果必须写回 HBM 再被下一个 kernel 读出来：

$$X = QK^T \quad\rightarrow\quad A = \text{softmax}(X) \quad\rightarrow\quad O = AV$$

具体来说：

1. **计算 $X = QK^T$**：从 HBM 读入 $Q$（形状 $L \times D$）和 $K$（形状 $L \times D$），计算得到 $X$（形状 $L \times L$），**写回 HBM**
2. **计算 $A = \text{softmax}(X)$**：从 HBM **重新读入** $X$，做 softmax，得到 $A$（形状 $L \times L$），**写回 HBM**
3. **计算 $O = AV$**：从 HBM **重新读入** $A$ 和 $V$，做矩阵乘法，得到最终输出 $O$

问题在于中间矩阵 $X$ 和 $A$ 的形状都是 $(L, L)$：

![Attention 矩阵形状](./assets/attention-matrix-shape.jpeg)

$L$ 一大（比如 128K），$(L, L)$ 矩阵完全放不进 SRAM，每步都要来回访问 HBM。三个 kernel 之间的 HBM 读写就成了瓶颈——计算本身不慢，**数据搬运慢**。

---

## GPU 内存层级

![GPU Memory Hierarchy](./assets/gpu-memory-hierarchy.png)

理解 Flash Attention 需要先理解 GPU 的内存层级：

- **SRAM**（片上缓存）：带宽 ~19 TB/s，但容量只有 ~20 MB。每个 SM 的 shared memory 属于这一层。
- **HBM**（显存）：带宽 ~1.5 TB/s，容量 ~40 GB（A100）。所有 tensor 默认住在这里。
- **DRAM**（主存）：带宽 ~12.8 GB/s，容量 >1 TB。CPU 侧内存，GPU 一般不直接访问。

SRAM 带宽是 HBM 的 **10 倍以上**，但容量差了 2000 倍。Flash Attention 的核心思路：既然 SRAM 快但小，就把大矩阵切成小块，每块在 SRAM 里算完再写回，减少 HBM 来回次数。

---

## 关键推导：如何把三步压成一步

标准 Attention 之所以要三个 kernel，是因为 softmax 需要看完整行才能算——你得先知道最大值和求和，才能归一化。下面的推导一步步消除这个依赖。

### Safe Softmax

直接用 $e^x$ 容易溢出（FP16 下 $x > 11$ 就溢出），所以先减去行最大值：

$$\text{softmax}(x_i) = \frac{e^{x_i - m}}{\sum_j e^{x_j - m}}, \quad m = \max_j x_j$$

朴素实现需要 **3 次遍历**整行：

```
pass 1: m = max(x_1, x_2, ..., x_N)         // 找最大值
pass 2: d = sum(exp(x_j - m) for j in 1..N)  // 求归一化因子
pass 3: a_i = exp(x_i - m) / d               // 计算每个元素
```

三次遍历意味着这行数据要从 HBM 读三次。能不能减少？

### Online Softmax（3-pass → 2-pass）

关键观察：pass 1 和 pass 2 能不能合并？问题是 pass 2 需要全局最大值 $m_N$，但 pass 1 还没算完的时候 $m$ 一直在变。

技巧：定义一个不依赖全局 $m_N$ 的**代理变量** $d'_i$：

$$d'_i = \sum_{j=1}^{i} e^{x_j - m_i}$$

注意这里用的是**局部最大值** $m_i = \max(x_1, ..., x_i)$，不是全局 $m_N$。当 $i = N$ 时 $d'_N = d$，就是我们要的归一化因子。

$d'_i$ 满足递推关系（推一下就能得到）：

$$d'_i = d'_{i-1} \cdot e^{m_{i-1} - m_i} + e^{x_i - m_i}$$

直觉：当看到新元素 $x_i$ 导致最大值从 $m_{i-1}$ 更新到 $m_i$ 时，之前累积的和 $d'_{i-1}$ 要乘以 $e^{m_{i-1} - m_i}$ 做修正（如果 $m_i > m_{i-1}$，这个因子 < 1，相当于把之前高估的部分压下来）。

现在 $m_i$ 和 $d'_i$ 可以在同一个循环里更新：

```
for i in 1..N:
    m[i]  = max(m[i-1], x[i])
    dp[i] = dp[i-1] * exp(m[i-1] - m[i]) + exp(x[i] - m[i])
```

把 3-pass 压成了 **2-pass**（上面这个循环是 pass 1，pass 2 用 $m_N$ 和 $d'_N$ 算每个元素）。

### Flash Attention（2-pass → 1-pass）

我们要的不只是 softmax 值，而是最终输出 $O = AV$。能不能把 pass 2 也并进来？

对第 $k$ 行定义**代理输出**：

$$o'_i = \sum_{j=1}^{i} \frac{e^{x_j - m_i}}{d'_i} V[j, :]$$

同样的修正思路，$o'_i$ 满足递推：

$$o'_i = o'_{i-1} \cdot \frac{d'_{i-1} \cdot e^{m_{i-1} - m_i}}{d'_i} + \frac{e^{x_i - m_i}}{d'_i} V[i, :]$$

直觉和 $d'$ 的修正类似：当最大值更新时，之前累积的加权和 $o'_{i-1}$ 也要同步修正。最终 $o'_N$ 就是精确的输出。

现在 $m_i$、$d'_i$、$o'_i$ 三者在**同一个循环**里更新，整个 Self-Attention 变成 **1-pass**：

```python
for i in 1..N:
    x[i]  = Q[k,:] @ K.T[:,i]
    m[i]  = max(m[i-1], x[i])
    dp[i] = dp[i-1] * exp(m[i-1]-m[i]) + exp(x[i]-m[i])
    op[i] = op[i-1] * dp[i-1] * exp(m[i-1]-m[i]) / dp[i]
    op[i] += exp(x[i]-m[i]) / dp[i] * V[i,:]
O[k,:] = op[N]
```

**内存占用**：循环中只需保存标量 $x_i$、$m_i$、$d'_i$ 和长度 $D$ 的向量 $o'_i$，总内存 $O(D)$，和序列长度 $N$ 无关。这就是为什么能把整个计算留在 SRAM 里。

### Tiling

上面的递推里，$d'$ 和 $o'$ 的更新全是加法和乘法，满足结合律。这意味着我们不需要逐元素推进，可以**按块**处理：把 $K$、$V$ 沿序列维度切成大小为 $B_c$ 的小块，每块加载进 SRAM 算完，再累加到 $o'$。

![Flash Attention Tiling](./assets/flash-attention-tiling.jpeg)

具体流程：

1. 外层循环遍历 Q 的每个块（大小 $B_r$）
2. 内层循环遍历 K、V 的每个块（大小 $B_c$）
3. 在 SRAM 中计算这个块的 $QK^T$、softmax（带修正）、乘 V
4. 累加到当前 Q 块对应的输出 $o'$

块大小的选择取决于 SRAM 容量：要同时放下 Q 块（$B_r \times D$）、K 块（$B_c \times D$）、V 块（$B_c \times D$）和中间结果（$B_r \times B_c$）。

| | HBM 访问量 | 显存占用 |
|--|--|--|
| 标准 Attention | $O(N^2)$ | $O(N^2)$ |
| Flash Attention | $O(N^2 / M)$ | $O(N)$ |

$M$ 是 SRAM 大小。HBM 访问减少了 $M$ 倍（A100 上约 100×），实际端到端加速约 **2–4×**（因为计算本身也有开销）。

---

## 实际场景：推荐系统中的 Attention 优化

推荐系统中大量使用 Transformer Encoder 做用户行为序列建模（比如直播间 summary 编码）。这类场景有个典型特点：batch 内各条序列长度差异很大，需要 padding 到同一长度。

```
seq1: [t1...t150]               ← 150 个真实 token
seq2: [t1...t80,  PAD×70]       ← 70 个 PAD 白白计算
seq3: [t1...t30,  PAD×120]      ← 120 个 PAD 白白计算
```

这里有两个独立的优化方向，可以分别做，也可以叠加：

| 优化方向 | 解决什么问题 | 手段 |
|--|--|--|
| **去 padding** | PAD token 参与了无效计算 | unpad → varlen → repad |
| **Flash Attention** | Attention 的 HBM 来回读写太多 | kernel fusion + tiling |

---

### 优化一：去 padding（unpad + varlen attention）

这个优化和 Flash Attention 无关，核心思想是：token $t_i$ 的输出只依赖同一序列里的其他 token，和 batch 索引无关：

$$\text{out}(t_i) = \sum_{j \in \text{same seq}} \text{softmax\_score}(t_i, t_j) \cdot V(t_j)$$

既然如此，可以把所有真实 token 物理拼成一条，用 `cu_seqlens` 记录序列边界，完全替代 batch 维度：

```
[seq1 tokens | seq2 tokens | seq3 tokens]  总长 = 260
cu_seqlens = [0, 150, 230, 260]
```

Attention kernel 保证 seq1 只 attend `[0, 150)`，seq2 只 attend `[150, 230)`。结果和 mask 方式完全等价，但省掉了所有 PAD 的无效计算。

#### FFN 不需要改

unpad 之后直接接 LayerNorm、FFN，不需要提前 repad：

```
(B, 150, 128)
      ↓  unpad_input（一次）
(total_tokens, 128)
      ↓  Attention（varlen）
      ↓  LayerNorm          ← token-wise，不需要知道边界
      ↓  FFN                ← nn.Linear 只看最后一维，shape 无关
      ↓  LayerNorm
      ↓  pad_input（一次）
(B, 150, 128)
```

FFN 权重形状是 `(128, 512)` 和 `(512, 128)`，没有序列长度维度。`(total_tokens, 128)` 和 `(B, 150, 128)` 逐 token 计算结果完全一致。

---

### 优化二：Flash Attention

即上文推导的 kernel fusion + tiling，把 Attention 的 HBM 访问从 $O(N^2)$ 降到 $O(N^2/M)$。这个优化对定长和变长序列都有效，和去不去 padding 是正交的。

---

### 叠加：Flash Attention + varlen

`flash_attn_varlen_func` 把两个优化合在一起——既用 `cu_seqlens` 跳过 padding，又用 tiling 减少 HBM 访问：

```python
from flash_attn.bert_padding import unpad_input, pad_input
from flash_attn import flash_attn_varlen_func

# x: (B, 150, 128)，attention_mask: (B, 150)
x_unpad, indices, cu_seqlens, max_seqlen = unpad_input(x, attention_mask)
# x_unpad: (total_real_tokens, 128)

q = q_proj(x_unpad).reshape(-1, 4, 32)
k = k_proj(x_unpad).reshape(-1, 4, 32)
v = v_proj(x_unpad).reshape(-1, 4, 32)

out = flash_attn_varlen_func(
    q, k, v,
    cu_seqlens_q=cu_seqlens, cu_seqlens_k=cu_seqlens,
    max_seqlen_q=max_seqlen, max_seqlen_k=max_seqlen,
    causal=False,
)

out = pad_input(out.reshape(-1, 128), indices, B, 150)
# → (B, 150, 128)
```

---

## 参考

- [FlashAttention 论文](https://arxiv.org/abs/2205.14135) — Dao et al., NeurIPS 2022
- [FlashAttention-2](https://arxiv.org/abs/2307.08691) — Dao, ICLR 2024
- [UW CSE 599M 课程笔记](https://courses.cs.washington.edu/courses/cse599m/23sp/notes/flashattn.pdf)
