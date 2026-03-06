---
title: "Flash Attention：从 Online Softmax 到变长序列"
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

标准实现分三步，中间结果要写回 HBM 再读出来：

$$X = QK^T \quad\rightarrow\quad A = \text{softmax}(X) \quad\rightarrow\quad O = AV$$

问题在于 $X$ 的形状是 $(L, L)$：

![Attention 矩阵形状](./assets/attention-matrix-shape.jpeg)

$L$ 一大（比如 128K），这个矩阵完全放不进 SRAM，每步都要来回访问 HBM，非常慢。

---

## GPU 内存层级

![GPU Memory Hierarchy](./assets/gpu-memory-hierarchy.png)

SRAM 带宽是 HBM 的 **10倍以上**，但容量只有 20MB。Flash Attention 的核心目标就是尽量把计算留在 SRAM 里，减少 HBM 来回次数。

---

## 关键推导：如何把三步压成一步

### Safe Softmax

直接用 $e^x$ 容易溢出（FP16 下 $x > 11$ 就溢出），所以先减去行最大值：

$$\text{softmax}(x_i) = \frac{e^{x_i - m}}{\sum_j e^{x_j - m}}, \quad m = \max_j x_j$$

朴素实现需要 3 次遍历：找最大值 → 求和 → 计算每个元素。

### Online Softmax（2-pass）

定义不依赖全局 $m_N$ 的代理变量 $d'_i$：

$$d'_i = \sum_{j=1}^{i} e^{x_j - m_i}$$

它满足如下递推（关键技巧）：

$$d'_i = d'_{i-1} \cdot e^{m_{i-1} - m_i} + e^{x_i - m_i}$$

这样 $m_i$ 和 $d'_i$ 可以在同一个循环里更新，把 3-pass 压成 2-pass。

### Flash Attention（1-pass）

我们要的不只是 softmax，而是最终输出 $O = AV$。对第 $k$ 行定义代理输出：

$$o'_i = \sum_{j=1}^{i} \frac{e^{x_j - m_i}}{d'_i} V[j, :]$$

递推形式：

$$o'_i = o'_{i-1} \cdot \frac{d'_{i-1} \cdot e^{m_{i-1} - m_i}}{d'_i} + \frac{e^{x_i - m_i}}{d'_i} V[i, :]$$

现在 $m_i$、$d'_i$、$o'_i$ 三者在**同一个循环**里更新，整个 Self-Attention 变成 1-pass：

```python
for i in 1..N:
    x[i]  = Q[k,:] @ K.T[:,i]
    m[i]  = max(m[i-1], x[i])
    dp[i] = dp[i-1] * exp(m[i-1]-m[i]) + exp(x[i]-m[i])
    op[i] = op[i-1] * dp[i-1] * exp(m[i-1]-m[i]) / dp[i]
    op[i] += exp(x[i]-m[i]) / dp[i] * V[i,:]
O[k,:] = op[N]
```

**内存占用**：循环中只需保存标量 $x_i$、$m_i$、$d'_i$ 和长度 $D$ 的向量 $o'_i$，总内存 $O(D)$，和序列长度无关。

### Tiling

上面的递推全是加法，满足结合律，可以直接 tiling：把 $K$、$V$ 按序列维度切成小块，每块在 SRAM 里完成计算再累加到 $o'$。

![Flash Attention Tiling](./assets/flash-attention-tiling.jpeg)

| | HBM 访问量 | 显存占用 |
|--|--|--|
| 标准 Attention | $O(N^2)$ | $O(N^2)$ |
| Flash Attention | $O(N^2 / M)$ | $O(N)$ |

$M$ 是 SRAM 大小，实际加速约 **2–4×**。

---

## 变长序列：unpad → varlen attention → repad

### 问题

实际场景（比如直播间 summary 编码）里，batch 内需要 padding 到同一长度：

```
seq1: [t1...t150]               ← 150 个真实 token
seq2: [t1...t80,  PAD×70]       ← 70 个 PAD 白白计算
seq3: [t1...t30,  PAD×120]      ← 120 个 PAD 白白计算
```

### 核心洞察：batch 维度只是工程打包

token $t_i$ 的输出只依赖同一序列里的其他 token，和 batch 索引无关：

$$\text{out}(t_i) = \sum_{j \in \text{same seq}} \text{softmax\_score}(t_i, t_j) \cdot V(t_j)$$

所以可以把所有真实 token 物理拼在一起，用 `cu_seqlens` 记录序列边界，完全替代 batch 维度：

```
[seq1 tokens | seq2 tokens | seq3 tokens]  总长 = 260
cu_seqlens = [0, 150, 230, 260]
```

Flash Attention kernel 保证 seq1 只 attend `[0, 150)`，seq2 只 attend `[150, 230)`。结果和 mask 方式完全等价，但省掉了所有 PAD 的无效计算。

### 代码

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

### FFN 不需要改

unpad 之后直接接 LayerNorm、FFN，不需要提前 repad：

```
(B, 150, 128)
      ↓  unpad_input（一次）
(total_tokens, 128)
      ↓  Flash Attn varlen
      ↓  LayerNorm          ← token-wise，不需要知道边界
      ↓  FFN                ← nn.Linear 只看最后一维，shape 无关
      ↓  LayerNorm
      ↓  pad_input（一次）
(B, 150, 128)
```

FFN 权重形状是 `(128, 512)` 和 `(512, 128)`，没有序列长度维度。`(total_tokens, 128)` 和 `(B, 150, 128)` 逐 token 计算结果完全一致。

---

## 参考

- [FlashAttention 论文](https://arxiv.org/abs/2205.14135) — Dao et al., NeurIPS 2022
- [FlashAttention-2](https://arxiv.org/abs/2307.08691) — Dao, ICLR 2024
- [UW CSE 599M 课程笔记](https://courses.cs.washington.edu/courses/cse599m/23sp/notes/flashattn.pdf)
