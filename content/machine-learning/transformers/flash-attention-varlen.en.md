---
title: "Flash Attention: From Online Softmax to Variable-Length Sequences"
date: 2026-03-05
tags:
  - Flash Attention
  - Transformer
  - GPU Optimization
lang: en
chinese: machine-learning/transformers/flash-attention-varlen
---

> 🌐 [中文版](./flash-attention-varlen.md)

## Core Concept

Flash Attention is an IO-aware implementation of Self-Attention. By using **kernel fusion + tiling**, it compresses the entire $QK^TV$ computation into a single GPU kernel, avoiding repeated HBM reads/writes and achieving significant speedup without any precision loss.

Algorithm evolution overview:

![Flash Attention Algorithm Evolution](./assets/flash-attention-overview.jpeg)

---

## Why Standard Attention Is Slow

The standard implementation has three steps, with intermediate results written back to HBM between each:

$$X = QK^T \quad\rightarrow\quad A = \text{softmax}(X) \quad\rightarrow\quad O = AV$$

The problem is that $X$ has shape $(L, L)$:

![Attention Matrix Shape](./assets/attention-matrix-shape.jpeg)

When $L$ is large (e.g., 128K), this matrix can't fit in SRAM at all. Each step requires round-trips to HBM, making it very slow.

---

## GPU Memory Hierarchy

<!-- TODO: add gpu-memory-hierarchy image -->

SRAM bandwidth is **10x+ higher** than HBM, but its capacity is only ~20MB. The core goal of Flash Attention is to keep computation in SRAM as much as possible, minimizing HBM round-trips.

---

## Key Derivation: Compressing Three Steps into One

### Safe Softmax

Using $e^x$ directly overflows easily (in FP16, $x > 11$ already overflows), so we subtract the row maximum first:

$$\text{softmax}(x_i) = \frac{e^{x_i - m}}{\sum_j e^{x_j - m}}, \quad m = \max_j x_j$$

The naive implementation requires 3 passes: find max → compute sum → compute each element.

### Online Softmax (2-pass)

Define a proxy variable $d'_i$ that doesn't depend on the global $m_N$:

$$d'_i = \sum_{j=1}^{i} e^{x_j - m_i}$$

It satisfies the following recurrence (the key trick):

$$d'_i = d'_{i-1} \cdot e^{m_{i-1} - m_i} + e^{x_i - m_i}$$

Now $m_i$ and $d'_i$ can be updated in the same loop, reducing 3-pass to 2-pass.

### Flash Attention (1-pass)

We need not just softmax, but the final output $O = AV$. For the $k$-th row, define a proxy output:

$$o'_i = \sum_{j=1}^{i} \frac{e^{x_j - m_i}}{d'_i} V[j, :]$$

Recurrence form:

$$o'_i = o'_{i-1} \cdot \frac{d'_{i-1} \cdot e^{m_{i-1} - m_i}}{d'_i} + \frac{e^{x_i - m_i}}{d'_i} V[i, :]$$

Now $m_i$, $d'_i$, and $o'_i$ are all updated in **a single loop**, making the entire Self-Attention 1-pass:

```python
for i in 1..N:
    x[i]  = Q[k,:] @ K.T[:,i]
    m[i]  = max(m[i-1], x[i])
    dp[i] = dp[i-1] * exp(m[i-1]-m[i]) + exp(x[i]-m[i])
    op[i] = op[i-1] * dp[i-1] * exp(m[i-1]-m[i]) / dp[i]
    op[i] += exp(x[i]-m[i]) / dp[i] * V[i,:]
O[k,:] = op[N]
```

**Memory usage**: The loop only needs scalars $x_i$, $m_i$, $d'_i$ and a vector $o'_i$ of length $D$ — total memory $O(D)$, independent of sequence length.

### Tiling

The recurrence above is purely additive and associative, so it can be directly tiled: split $K$ and $V$ along the sequence dimension into small blocks, compute each block in SRAM, and accumulate into $o'$.

![Flash Attention Tiling](./assets/flash-attention-tiling.jpeg)

| | HBM Access | Memory Usage |
|--|--|--|
| Standard Attention | $O(N^2)$ | $O(N^2)$ |
| Flash Attention | $O(N^2 / M)$ | $O(N)$ |

$M$ is the SRAM size. In practice, this yields roughly **2–4× speedup**.

---

## Variable-Length Sequences: unpad → varlen attention → repad

### The Problem

In real-world scenarios (e.g., encoding livestream summaries), sequences in a batch must be padded to the same length:

```
seq1: [t1...t150]               ← 150 real tokens
seq2: [t1...t80,  PAD×70]       ← 70 PADs wasted
seq3: [t1...t30,  PAD×120]      ← 120 PADs wasted
```

### Key Insight: The Batch Dimension Is Just Engineering Packaging

Token $t_i$'s output only depends on other tokens in the same sequence, regardless of batch index:

$$\text{out}(t_i) = \sum_{j \in \text{same seq}} \text{softmax\_score}(t_i, t_j) \cdot V(t_j)$$

So we can physically concatenate all real tokens and use `cu_seqlens` to record sequence boundaries, completely replacing the batch dimension:

```
[seq1 tokens | seq2 tokens | seq3 tokens]  total = 260
cu_seqlens = [0, 150, 230, 260]
```

The Flash Attention kernel ensures seq1 only attends to `[0, 150)`, seq2 only to `[150, 230)`. The result is equivalent to masking, but eliminates all wasted computation on PAD tokens.

### Code

```python
from flash_attn.bert_padding import unpad_input, pad_input
from flash_attn import flash_attn_varlen_func

# x: (B, 150, 128), attention_mask: (B, 150)
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

### FFN Doesn't Need Changes

After unpadding, you can directly apply LayerNorm and FFN without re-padding first:

```
(B, 150, 128)
      ↓  unpad_input (once)
(total_tokens, 128)
      ↓  Flash Attn varlen
      ↓  LayerNorm          ← token-wise, no boundary info needed
      ↓  FFN                ← nn.Linear only sees last dim, shape-agnostic
      ↓  LayerNorm
      ↓  pad_input (once)
(B, 150, 128)
```

FFN weights have shape `(128, 512)` and `(512, 128)` — no sequence length dimension. Computing on `(total_tokens, 128)` vs `(B, 150, 128)` gives identical per-token results.

---

## References

- [FlashAttention Paper](https://arxiv.org/abs/2205.14135) — Dao et al., NeurIPS 2022
- [FlashAttention-2](https://arxiv.org/abs/2307.08691) — Dao, ICLR 2024
- [UW CSE 599M Lecture Notes](https://courses.cs.washington.edu/courses/cse599m/23sp/notes/flashattn.pdf)
