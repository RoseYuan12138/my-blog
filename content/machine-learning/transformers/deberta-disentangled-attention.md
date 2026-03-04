---
title: "拆解 DeBERTa：它比 Transformer 多了什么？"
date: 2026-03-03
tags:
  - DeBERTa
  - Transformer
  - Attention
  - NLP
  - 位置编码
lang: zh
english: machine-learning/transformers/deberta-disentangled-attention.en
---

> 🌐 [Read in English](./deberta-disentangled-attention.en.md)

---

## 一、先回顾 Vanilla Transformer 的位置编码

Vanilla Transformer（BERT）的做法是：在输入层把位置信息和内容**混在一起**。

```
输入 = word_embedding + position_embedding + token_type_embedding
                                 ↑
              加完就混了，后续 attention 无法区分
         "这个信号来自内容" 还是 "来自位置"
```

这意味着 Self-Attention 计算 `Q × K^T` 时：

```
Q = (content + position) × W_Q
K = (content + position) × W_K

Q × K^T 展开后有 4 项：
= content_i × content_j   ← 内容和内容的关系 ✓
+ content_i × position_j  ← 内容和位置的关系 ✓
+ position_i × content_j  ← 位置和内容的关系 ✓
+ position_i × position_j ← 位置和位置的关系（其实没啥用）
```

四项纠缠在一起，模型需要自己学会分解它们。更棘手的是：用的是**绝对位置**（position 0, 1, 2, ...），模型学到的是"位置 3 的 token"，而不是"距离我 2 个位置的 token"。这给长度泛化造成了根本性障碍。

---

## 二、DeBERTa 的核心创新：Disentangled Attention

DeBERTa 的论文标题是 **D**ecoding-**e**nhanced **BERT** with **D**isentangled **A**ttention。核心是两个词：**Disentangled（解耦）** 和 **Decoding-enhanced（增强解码）**。

### 2.1 把内容和位置彻底分开

DeBERTa 在 encoder 阶段**不把位置加到内容里**。取而代之的是，维护一套独立的**相对位置 embedding 表**，在每一层 attention 时单独传入：

```python
# 相对位置 embedding 表
# 范围：[-max_relative_positions, +max_relative_positions]
rel_embedding_table: shape = (2 × max_relative_positions, hidden_size)

# 每次 attention 时，根据序列长度切取对应范围
att_span = min(seq_length, max_relative_positions)
indices = range(max_relative_positions - att_span, max_relative_positions + att_span)
relative_embeddings = rel_embedding_table[indices]
```

### 2.2 Attention 分解为三项

在每一层 Self-Attention 中，DeBERTa 把注意力得分拆成**三个独立的项**：

```
Score(i, j) =
  H_i·W_q × (H_j·W_k)^T          ← ① Content-to-Content (C2C)
                                       "token i 的内容关注 token j 的内容"
+ H_i·W_q × (P_{i→j}·W_k_r)^T   ← ② Content-to-Position (C2P)
                                       "token i 的内容关注与 j 的相对距离"
+ (P_{j→i}·W_q_r) × (H_j·W_k)^T ← ③ Position-to-Content (P2C)
                                       "token j 的位置关注 token i 的内容"
```

其中 `P_{i→j}` 表示 token i 相对于 token j 的**相对位置 embedding**（对应距离 i-j 的向量）。

**为什么去掉了第四项 Position-to-Position (P2P)？**

"位置 3 和位置 7 的距离"是固定常数，不携带任何关于输入内容的信息，对 attention 的动态分配没有帮助，因此直接舍弃。

### 2.3 为什么用相对位置而不是绝对位置

```
绝对位置：
  "我是位置 3"  "你是位置 7"
  → 模型需要从 (3, 7) 推断出 "距离 = 4"
  → 换个句子位置就得重新学

相对位置：
  "你在我右边 4 个位置"
  → 直接编码距离关系
  → 不管绝对位置在哪，距离关系不变
  → 天然支持比训练时更长的序列
```

---

## 三、Enhanced Mask Decoder (EMD)

DeBERTa 的第二个创新：**绝对位置信息延迟注入**。

### 3.1 为什么还需要绝对位置

相对位置能捕捉 token 之间的距离关系，但有些任务需要绝对位置信息。以 MLM（完形填空）为例：

```
"The [MASK] is the capital of France"
[MASK] 在句首（位置 1）→ 更可能是名词短语，如 "city"
[MASK] 在句子后半段   → 候选词分布完全不同
```

如果完全没有绝对位置信息，某些预测会丢失重要线索。

### 3.2 延迟注入：最后再加绝对位置

DeBERTa 的解法是在最后一步才引入绝对位置，而不是从输入层就混入：

```
Vanilla BERT：
  输入层 → [content + abs_position] → Encoder N层 → 输出
                        ↑
              一开始就混入，后续无法分离

DeBERTa：
  输入层 → [content only] → Encoder N层 → [注入 abs_position] → EMD Decoder 1层 → 输出
                ↑                                    ↑
           只用相对位置               最后才加绝对位置（仅 MLM 预训练时使用）
```

> **注意**：在非 MLM 的下游任务（如排序、分类、推荐）中，EMD Decoder 通常不参与前向传播，只走 Encoder 阶段即可。

---

## 四、DeBERTa 和 Vanilla Transformer 对比总结

```
┌──────────────────────────────────────────────────────────────┐
│              Vanilla Transformer (BERT)                      │
│                                                              │
│  Input = word_emb + abs_position_emb + token_type_emb       │
│                         ↓                                    │
│  ┌──────────────────────────────┐                           │
│  │ Self-Attention               │                           │
│  │ Q×K^T（content+position 混） │ ← 内容和位置纠缠           │
│  ├──────────────────────────────┤                           │
│  │ FFN                          │                           │
│  └──────────────────────────────┘ × N layers                │
│                         ↓                                    │
│               Pooled Output                                  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                       DeBERTa                                │
│                                                              │
│  Input = word_emb + token_type_emb（无绝对位置！）            │
│  Relative Position Embedding（独立维护）                      │
│                         ↓                                    │
│  ┌──────────────────────────────┐                           │
│  │ Disentangled Attention       │                           │
│  │ Score = C2C + C2P + P2C     │ ← 内容位置解耦，相对位置    │
│  ├──────────────────────────────┤                           │
│  │ FFN                          │                           │
│  └──────────────────────────────┘ × N layers (Encoder)      │
│                         ↓                                    │
│  [加入绝对位置] → EMD Decoder 1层（仅 MLM 预训练时使用）      │
│                         ↓                                    │
│               Pooled Output (position 0)                     │
└──────────────────────────────────────────────────────────────┘
```

|  | Vanilla Transformer (BERT) | DeBERTa |
|---|---|---|
| 位置编码方式 | 绝对位置（sin/cos 或 learned） | **相对位置**（learned） |
| 位置注入时机 | 输入层一开始就加入 | **Encoder 不加，Decoder 才加** |
| Attention 计算 | Q×K^T 一次算完（4 项纠缠） | **拆成 C2C + C2P + P2C 三项** |
| 内容与位置关系 | 纠缠在一起 | **解耦（Disentangled）** |
| 长度泛化 | 受绝对位置表大小限制 | **相对位置天然支持更长序列** |
| 额外参数 | 无 | 相对位置 embedding 表 ≈ 0.1~0.8M |

---

## 五、对 FLOPs 的影响

Disentangled Attention 需要算**三次** attention score（C2C, C2P, P2C），而 vanilla 只算一次：

```
Vanilla 每层：  24Sh² + 4S²h
DeBERTa 每层：  24Sh² + 4S²h × 3  ← attention score 部分 ×3
             = 24Sh² + 12S²h

当 h >> S 时（多数情况），差异很小。
当 S 很长时，DeBERTa 的 attention 开销 ×3 才会明显。
```

| 配置 | Vanilla FLOPs/层 | DeBERTa FLOPs/层 | 差异 |
|------|:---:|:---:|:---:|
| h=128, S=40 | 8.27M | 8.91M | +8% |
| h=128, S=150 | 12.77M | 17.69M | +39% |
| h=768, S=150 | 274.1M | 274.3M | +0.07% |

**结论**：hidden_dim 越大，Disentangled Attention 的额外开销占比越小。在 h=768 时几乎可以忽略。

额外参数方面，DeBERTa 多了一个相对位置 embedding 表：

```
参数量 = 2 × max_relative_positions × hidden_size
max_relative_positions = 512（默认）:
  h=128: 2 × 512 × 128 = 131K ≈ 0.13M
  h=768: 2 × 512 × 768 = 786K ≈ 0.8M
```

相比每层 12h² 的参数量（h=128 时约 0.2M/层），增加不大。

---

## 六、在推荐系统中应用 DeBERTa

将 DeBERTa 用于推荐系统序列建模时，有几处关键的结构适配值得注意。

### 6.1 输入不再是 token id，而是预训练 embedding

在 NLP 中，DeBERTa 的输入是 token id，内部有一个 embedding lookup table（vocab × hidden_size）。在推荐场景下，item/user 的 embedding 通常已经通过其他方式（如协同过滤、行为序列预训练）得到，可以直接替换 embedding lookup 层：

```python
# NLP 原版：token id → embedding lookup → (B, S, h)
word_emb = embedding_table[token_ids]

# 推荐系统适配：直接传入预训练好的 item embedding
# input_tensor shape: (B, S, h)
encoder_input = input_tensor  # 跳过 lookup，直接作为 encoder 输入
```

### 6.2 不需要 EMD Decoder

推荐系统的序列建模任务（点击率预估、排序）不需要做 MLM，因此只走 Encoder 阶段：

```python
encoder_output = deberta_encoder(
    input_tensor,
    relative_embeddings=rel_emb,
    attention_mask=mask
)  # shape: (B, S, h)

# 取 position 0 作为序列表征（类似 [CLS]）
pooled = dense(encoder_output[:, 0, :])  # shape: (B, h)
```

### 6.3 相对位置的语义适配

在行为序列中，相对位置的语义是**时间距离**：用户在当前 item 之前 k 步交互的 item。相对位置编码天然契合这一语义——用户的近期行为比远期行为更相关，而这正是相对距离能直接建模的东西，绝对位置（"这是第 7 次点击"）反而意义不大。

> **实践建议**：将 `max_relative_positions` 设置为行为序列的最大长度（如 50~200），保证所有 item 对之间的相对距离都在 embedding 表的覆盖范围内。

### 6.4 Pooled Output 的语义

没有显式的 `[CLS]` token 时，position 0 经过多层 self-attention 后，已经通过注意力机制聚合了整个序列的信息。最后再过一个 Dense 层做非线性变换，得到的向量即可作为序列的整体表征，送入后续的排序网络。

---

*参考：[DeBERTa: Decoding-enhanced BERT with Disentangled Attention](https://arxiv.org/abs/2006.03654)，He et al., ICLR 2021*
