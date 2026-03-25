---
title: "RecGPT: 顺序推荐的基础模型"
date: 2026-03-25
tags:
  - 推荐系统
  - 基础模型
  - 跨域泛化
lang: zh
english: recgpt-foundation-model-sequential-recommendation.en
---

> 🌐 [Read in English](./recgpt-foundation-model-sequential-recommendation.en.md)

论文精读笔记：[A Foundation Model for Sequential Recommendation](https://arxiv.org/abs/2506.06270)

**作者**: Yangqin Jiang, Xubin Ren, Lianghao Xia, Da Luo, Kangyi Lin, Chao Huang (香港大学 & 腾讯)

**代码**: [https://github.com/HKUDS/RecGPT](https://github.com/HKUDS/RecGPT)

---

## 核心思路

### 问题：推荐系统为什么需要基础模型？

传统推荐系统（SASRec、BERT4Rec 等）的核心表示方式是 **item ID embedding**——每个物品一个独立向量。这带来三个根本性问题：

1. **冷启动失败**：新物品没有交互历史，ID embedding 无法学到有意义的表示
2. **跨域不可迁移**：Amazon 上学到的 embedding 对 Yelp 完全没用，因为 ID 空间不共享
3. **每换一个域就要重新训练**：成本高，不现实

NLP 和 CV 领域早已通过基础模型（GPT、ViT）解决了跨域泛化问题。核心洞察是：**统一的 token 化 + 自回归建模 = 跨域泛化能力**。那推荐系统能不能也这样做？

### 解决方案：RecGPT

RecGPT 的核心思路是：**把顺序推荐问题重新表述为 next-token prediction 问题**。

但直接套用语言模型的方案行不通，因为面临三个独特挑战：

| 挑战 | 语言模型 | 推荐系统 |
|------|---------|---------|
| Token 化 | 词汇表固定，BPE/SentencePiece | 物品描述异构，跨域格式不同 |
| 注意力 | Token 之间是平等的 | Item 内 token 需要双向交互，item 间需要因果关系 |
| 解码 | 词汇表有限（~50K） | Token 组合空间巨大（$L^{d_{fsq}}$），但有效物品数量远小于此 |

RecGPT 针对每个挑战分别设计了解决方案：
- **Finite Scalar Quantization (FSQ)** → 统一的 item token 化
- **混合双向-因果注意力** → 正确建模层次依赖
- **目录感知 Beam Search + Trie** → 高效解码

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RecGPT 架构总览                               │
├──────────────────┬──────────────────────┬───────────────────────────┤
│  (i) 统一 Item    │  (ii) 通用推荐建模     │  (iii) 高效 Token 解码    │
│     Token 化      │                      │                           │
│                  │                      │                           │
│  Item Text       │   Token Embed Table  │   Beam Search             │
│    ↓             │        ↓             │      ↓                    │
│  MPNet Encoder   │   Aux Embed (连续)    │   Trie 前缀约束            │
│    ↓             │        ↓             │      ↓                    │
│  连续 Embedding   │   LNorm + Sum + Pos  │   候选过滤                 │
│    ↓             │        ↓             │      ↓                    │
│  FSQ 量化         │   Transformer Layers │   Top-K Items             │
│    ↓             │   (混合注意力)         │                           │
│  离散 Token 序列   │        ↓             │                           │
│                  │   Autoregressive Loss│                           │
└──────────────────┴──────────────────────┴───────────────────────────┘
```

---

## 方法细节

### 2.1 统一 Item Token 化

#### 2.1.1 文本编码

RecGPT 使用 **MPNet** 作为文本编码器，将物品的文本特征（标题、类别、描述等）编码为连续向量。MPNet 的优势是同时融合了 Masked Language Modeling (MLM) 和 Permuted Language Modeling (PLM)。

MPNet 的训练目标：

$$\mathbb{E}_{z \in \mathcal{Z}_n} \sum_{t=c+1}^{n} \log P(x_{z_t} | x_{z_{<t}}, \Phi_{z_{>c}}; \theta)$$

其中 $\mathcal{Z}_n$ 是索引 $(1, \cdots, n)$ 的排列集合，$z_t$ 是排列中第 $t$ 个索引，$\Phi_{z_{>c}}$ 是位置 $z_{>c}$ 处的 mask。

编码后，每个物品 $i$ 得到一个 $d_L$ 维向量：

$$e_i = \text{MPNet}(X_i), \quad e_i \in \mathbb{R}^{d_L}$$

**为什么用文本而不是 ID？** 因为文本是"域无关的"——无论是 Amazon 的商品标题还是 Yelp 的餐厅名称，文本编码器都能提取语义。这是跨域泛化的基础。

#### 2.1.2 Finite Scalar Quantization (FSQ)

这是 RecGPT 最核心的创新之一。目标是把连续的文本 embedding **离散化为 token 序列**，从而可以用自回归模型建模。

**步骤**：

1. **分割**：将 $d_L$ 维的 $e_i$ 分成 $K$ 个子向量 $e_i^k \in \mathbb{R}^{d_L/K}$
2. **降维**：线性变换 $T_{in}(e_i^k) = W_{in} e_i^k + b$，从 $d_L/K$ 降到 $d_{fsq}$
3. **归一化**：Sigmoid 函数 $\sigma(\cdot)$ 把值映射到 $(0, 1)$
4. **离散化**：四舍五入到 $\{0, 1, \ldots, L-1\}$ 中的整数

$$\text{FSQ}(e_i^k) = R[(L-1)\sigma(T_{in}(e_i^k))]$$

其中 $R[\cdot]$ 是四舍五入操作，$L$ 是量化级别数。每个子向量被量化到 $d_{fsq}$ 维的整数向量，codebook 大小为 $|C| = L^{d_{fsq}}$。

**梯度怎么办？** 四舍五入不可微，用 **Straight-Through Estimator (STE)**：

$$\text{FSQ}(e_i^k) = (L-1)\sigma(T_{in}(e_i^k)) + \text{sg}[R[(L-1)\sigma(T_{in}(e_i^k))] - (L-1)\sigma(T_{in}(e_i^k))]$$

$\text{sg}[\cdot]$ 是 stop gradient 操作，前向传播用离散值，反向传播梯度直通。

**为什么选 FSQ 而不是 VQ-VAE？** FSQ 优雅地解决了 VQ-VAE 的 **codebook collapse** 问题（即大部分 code 不被使用）。FSQ 不需要维护显式的 codebook，每个维度独立量化，天然避免了坍缩。

**具体配置**：$d_{fsq} = 5$，量化级别 $L = [8, 8, 8, 6, 5]$，codebook 大小 $= 8 \times 8 \times 8 \times 6 \times 5 = 15360$。每个 item 用 $K = 4$ 个 token 表示。

#### 2.1.3 量化优化

量化后需要能重建原始 embedding，训练一个多层 Transformer 解码器做重建，用 **L1 损失**：

$$\mathcal{L}_{fsq} = \sum_{i=0}^{N-1} \| e_i - \text{Decoder}([T_{out}(\hat{e}_i^0), \cdots, T_{out}(\hat{e}_i^{K-1})]) \|_1$$

其中 $\hat{e}_i^k$ 是量化后的表示，$T_{out}$ 是维度扩展变换（从 $d_{fsq}$ 回到 $d_L/K$）。用 L1 而非 L2 是因为 L1 对异常值更鲁棒，有利于保持区分性语义特征。

### 2.2 通用推荐建模

#### 2.2.1 混合双向-因果注意力

这是 RecGPT 的第二个核心创新。问题是：当一个 item 由多个 token 表示时，标准的因果注意力（GPT 风格）会限制同一 item 内 token 之间的信息流动。

解决方案：**双层注意力机制**
- **Intra-item（物品内）**: 双向注意力——同一物品的 token 之间可以自由交换信息
- **Inter-item（物品间）**: 因果注意力——只能看到之前的物品，维持时序因果性

```
Item 1 tokens: [t1, t2, t3, t4]    Item 2 tokens: [t5, t6, t7, t8]
              ←→ 双向 ←→                        ←→ 双向 ←→
                    |                                  |
                    └────── 因果（只能向右看）──────────→
```

**为什么需要这样？** 语言模型中每个 token 是独立的"词"，但在 RecGPT 中，4 个 token 共同表示一个物品。如果 token $t_2$ 看不到 $t_3$ 和 $t_4$（因为因果 mask），就无法形成完整的物品表示。双向注意力解决了这个问题。

#### 2.2.2 辅助语义特征

量化必然有信息损失。RecGPT 通过**双流表示**来缓解：

- **Token embeddings** $E_{wte} \in \mathbb{R}^{T \times d_{ar}}$：离散 token 的 embedding（学到的）
- **Auxiliary embeddings** $E_{aux} \in \mathbb{R}^{T \times d_{ar}}$：原始连续语义特征的线性投影

最终输入是两者加上位置编码的融合：

$$X = \text{LNorm}(E_{aux}) + \text{LNorm}(E_{wte}) + E_{wpe}$$

其中 $E_{wpe} \in \mathbb{R}^{T \times d_{ar}}$ 是位置 embedding。用 LayerNorm 分别归一化两个流，保证数值稳定。

### 2.3 训练目标

标准的自回归 next-token prediction loss：

$$\mathcal{L}_{ar} = -\sum_{t=0}^{T-1} \log P\left(Y_t \mid X_{< \lfloor \frac{t}{K} \rfloor \times K}\right)$$

关键细节：$\lfloor \frac{t}{K} \rfloor \times K$ 确保在预测第 $t$ 个 token 时，只能看到前面**完整 item** 的所有 token（不是前面所有 token）。结合双向注意力，模型在训练时可以**同时预测**下一个 item 的所有 $K$ 个 token。

### 2.4 高效 Item Token 解码

#### 2.4.1 Beam Search

推理时，RecGPT 在一次前向传播中**并行预测** $K$ 个 token（因为双向注意力的设计），然后用 beam search 在这 $K$ 个 token 的联合概率分布上搜索 top-n 最可能的 token 序列。

#### 2.4.2 Trie-based 目录感知约束

核心洞察：理论上 token 组合空间有 $L^{d_{fsq}} = 15360^4$ 种可能，但实际目录中只有几十万到几百万个物品。

做法：把目录中所有物品的 token 序列构建成一棵 **Trie（前缀树）**。Beam search 每生成一个 token，就在 Trie 上查找，只保留能到达有效物品的分支。

好处：
1. 不浪费计算在无效的 token 组合上
2. 保证推荐结果一定是目录中的真实物品

---

## 实验设置

### 数据集

| 数据集 | #用户 | #物品 | #交互 | 平均序列长度 |
|--------|-------|-------|-------|-------------|
| **预训练（11 个 Amazon 子类）** | 12,472,073 | 15,491,643 | 131,657,450 | 10.56 |
| - Books | 1,091,587 | 2,978,216 | 13,859,969 | 12.69 |
| - Clothing | 3,088,673 | 4,875,707 | 30,245,204 | 9.79 |
| - Electronics | 1,692,840 | 1,128,480 | 16,248,100 | 9.59 |
| - Kitchen | 3,096,330 | 2,742,128 | 30,758,013 | 9.93 |
| **验证（3 个 Amazon 子类）** | 184,674 | 377,186 | 1,615,405 | 8.75 |
| **测试 - Amazon** | | | | |
| Baby | 184,851 | 123,537 | 1,551,060 | 8.39 |
| Games | 117,742 | 83,137 | 1,030,529 | 8.75 |
| Office | 333,744 | 363,786 | 2,735,472 | 8.19 |
| **测试 - 跨平台** | | | | |
| Yelp | 287,116 | 148,523 | 4,392,168 | 15.29 |
| Washington | 625,428 | 120,080 | 12,382,314 | 19.79 |
| Steam | 334,594 | 15,066 | 4,214,640 | 12.59 |

预训练数据规模：**1.3 亿条交互**，覆盖 11 个 Amazon 产品类别。

### 模型配置

- 最大序列长度 $T = 1024$，隐藏维度 $d_{ar} = 768$
- 位置 embedding 维度：$\mathbb{R}^{1025 \times 768}$
- FSQ：$d_{fsq} = 5$, $L = [8,8,8,6,5]$, 词汇表大小 15,360
- 每个 item 用 $K = 4$ 个 token 表示
- 解码器：GPT-2 架构，3 层 Transformer
- Token embedding table: $\mathbb{R}^{15360 \times 768}$
- 训练硬件：4 × A100 40G（也验证了单张 RTX 3090 24G 可行）

### Baseline

9 个传统方法 + 6 个预训练方法：

- **RNN**: GRU4Rec, GRU4RecF
- **CNN**: Caser
- **Transformer**: BERT4Rec, FDSA
- **对比学习**: CL4SRec, DuoRec, ICLRec, MAERec
- **预训练**: S3-Rec, UniSRec, VQ-Rec, TIGER, RecFormer, IDGenRec

---

## 实验结果

### Zero-shot 跨域推荐（Table 1）

RecGPT **不使用任何目标域训练数据**（zero-shot），对比其他方法使用 **10% 目标域数据**（few-shot）。

**Amazon 同平台跨域**（部分关键指标）：

| 数据集 | 指标 | 最佳 Baseline | RecGPT (zero-shot) | 提升 |
|--------|------|---------------|-------------------|------|
| Baby | Hit@1 | 0.0025 (多个方法) | **0.0273** | ~10× |
| Baby | NDCG@5 | 0.0063 (DuoRec) | **0.0279** | ~4.4× |
| Games | Hit@1 | 0.0045 (CL4SRec) | **0.0364** | ~8× |
| Games | NDCG@5 | 0.0103 (CL4SRec) | **0.0371** | ~3.6× |
| Office | Hit@1 | 0.0022 (DuoRec) | **0.0280** | ~12.7× |
| Office | NDCG@5 | 0.0041 (FDSA) | **0.0290** | ~7× |

**跨平台**（部分关键指标）：

| 数据集 | 指标 | 最佳 Baseline | RecGPT (zero-shot) | 提升 |
|--------|------|---------------|-------------------|------|
| Yelp | Hit@1 | 0.0029 (MAERec) | **0.0161** | ~5.6× |
| Yelp | NDCG@5 | 0.0074 (MAERec) | **0.0163** | ~2.2× |
| Washington | Hit@1 | 0.0041 (MAERec) | **0.0122** | ~3× |
| Steam | Hit@1 | 0.1022 (FDSA) | **0.1237** | ~1.2× |
| Steam | NDCG@5 | 0.1232 (FDSA) | **0.1245** | ~1.01× |

关键发现：
- 在 Amazon 子域上优势巨大（10× 以上的 Hit@1 提升），因为预训练数据同为 Amazon 系列
- 跨平台（Yelp、Washington）优势明显但较小，说明平台差异是真实的
- Steam 数据集上 FDSA 的 few-shot 已经很强（0.1022 Hit@1），RecGPT 仍能超过（0.1237），但优势收窄

### 冷启动推荐（Table 2）

每个用户只保留 1-3 条交互历史，预测下一个交互。

| 数据集 | 指标 | 最佳 Baseline | RecGPT | 
|--------|------|---------------|--------|
| Baby | Hit@1 | 0.0099 (DuoRec) | **0.0165** |
| Baby | NDCG@5 | 0.0153 (DuoRec) | **0.0169** |
| Office | Hit@1 | 0.0096 (DuoRec) | **0.0188** |
| Office | NDCG@5 | 0.0154 (DuoRec) | **0.0197** |
| Yelp | Hit@1 | 0.0063 (DuoRec) | **0.0126** |
| Yelp | NDCG@5 | 0.0141 (DuoRec) | **0.0128** |

注意：Yelp 的 Hit@3/5 上 RecGPT 并不总是最佳（FDSA、DuoRec 等在 Hit@5 上达到 0.0219-0.0221），说明 RecGPT 在极端冷启动下虽然 Hit@1 强，但在更宽松的指标下优势减小。

### 工业部署验证

在一个拥有数百万日活的新闻推荐平台上验证：
- 163,385 用户，455,372 内容，999,140 交互记录
- RecGPT 在 Hit@5 和 NDCG@5 上均显著优于所有 baseline（包括 BERT4Rec、FDSA、CL4SRec、DuoRec、MAERec、S3-Rec）

### 与预训练推荐方法对比（Figure 6 & 7）

RecGPT 在 Baby、Office、Yelp 上的 Hit@5 和 NDCG@5 均超过 S3-Rec、UniSRec、VQ-Rec、TIGER、IDGenRec、RecFormer。

**关键控制实验**：
- **RecGPT-10%**（只用 10% 训练数据，参数量也减少）仍然超过原始 VQ-Rec
- **VQ-Rec (Re-trained)**（用 RecGPT 的全部数据重新训练 VQ-Rec）反而性能下降

这证明 RecGPT 的优势不仅来自数据规模，更来自**架构设计**（decoder-only + 自回归目标）。

---

## Ablation 分析（Table 3）

| 变体 | Baby Hit@5 | Baby NDCG@5 | Office Hit@5 | Office NDCG@5 | Yelp Hit@5 | Yelp NDCG@5 |
|------|-----------|-------------|-------------|--------------|-----------|-------------|
| w/o FSQ | 0.0178 | 0.0177 | 0.0167 | 0.0166 | 0.0139 | 0.0138 |
| w/o Bidir | 0.0279 | 0.0275 | 0.0288 | 0.0283 | 0.0162 | 0.0158 |
| w/o Aux | 0.0191 | 0.0189 | 0.0205 | 0.0200 | 0.0075 | 0.0065 |
| w/o Pref | 0.0282 | 0.0274 | 0.0281 | 0.0280 | 0.0162 | 0.0161 |
| **RecGPT** | **0.0283** | **0.0279** | **0.0299** | **0.0290** | **0.0166** | **0.0163** |

**各组件影响分析**：

1. **FSQ 是最关键的**：去掉 FSQ（用随机 token）导致最大幅度下降。Baby Hit@5 从 0.0283 降到 0.0178（-37%），Office 从 0.0299 降到 0.0167（-44%）。语义保持的 token 化是跨域泛化的基石。

2. **辅助语义特征很重要**：去掉 Aux 后，Yelp NDCG@5 从 0.0163 降到 0.0065（-60%），说明量化信息损失在跨平台场景下影响尤为严重。

3. **双向注意力有帮助但不是决定性的**：去掉 Bidir，Baby 下降很小（0.0283→0.0279），但 Office 下降明显（0.0299→0.0288）。

4. **Trie 前缀约束影响最小**：w/o Pref 的下降很小，说明它主要提升效率而非质量。

### Scaling Law（Figure 4 & 5）

用 5%, 10%, 25%, 50%, 100% 的训练数据分别训练：

- **关键发现**：10% → 25% 之间有一个不成比例的性能跃升，暗示存在一个"涌现能力阈值"
- 评估 loss 随训练 token 数呈 **power-law 下降**（与 LLM 的 scaling law 一致）
- 通过 power-law 拟合 5%-50% 的数据点，可以准确预测 100% 数据时的性能

实际意义：**扩大训练数据比增大模型更高效**——这对工业部署很重要，因为不增加推理成本。

---

## 值得思考的点

### 1. FSQ vs VQ-VAE：简单就是好？

RecGPT 选择 FSQ 而非更常见的 VQ-VAE/RQ 是一个有意思的决定。FSQ 本质上是"把每个维度独立量化到几个整数"，看起来粗暴但优雅地避免了 codebook collapse。这让我想到一个更广泛的趋势：**在大规模系统中，简单、稳定的方法往往优于精巧但脆弱的方法**。VQ-Rec 用了 VQ 但在扩大数据后反而性能下降，很可能就是 codebook 管理出了问题。

### 2. 跨平台泛化的真实天花板

虽然 RecGPT 在 Amazon 子域间的泛化效果惊人（10× 提升），但跨平台（Amazon→Yelp/Steam）时优势明显缩小。这说明**文本语义并不能完全捕捉推荐行为的差异**——人们在电商上的浏览模式和在游戏平台上的选择模式本质不同。文本只是物品的一个方面，行为模式（browsing vs. purchasing vs. rating）可能需要额外建模。

### 3. 4 个 token 够吗？

每个 item 用 $K=4$ 个 token 表示，codebook 大小 15,360。理论上可以区分 $15360^4 \approx 5.6 \times 10^{16}$ 个物品，远超实际需求。但问题是：**4 个 token 能否充分编码一个物品的语义？** 论文没有做 $K$ 的消融实验。直觉上，$K$ 太小会损失信息，太大会让序列过长影响效率。这个 trade-off 值得深入研究。

### 4. 自回归 vs 双向：推荐的正确范式？

RecGPT 用 decoder-only 架构 + 自回归目标，对标 GPT。但 BERT4Rec 用的是 encoder + MLM（类似 BERT），也曾证明在推荐中双向编码更好。RecGPT 的混合注意力实际上是在自回归框架里"偷渡"了双向信息（item 内）。一个自然的问题是：**如果用完全双向的 encoder 架构 + FSQ token 化，效果会不会更好？** 论文没有探讨这个方向。

### 5. 工业部署的现实考量

论文提到 RecGPT 已部署在腾讯的新闻推荐平台，但细节很少。实际部署中几个关键问题：
- **Trie 的更新频率**：新物品上线时，Trie 需要重建还是增量更新？
- **推理延迟**：Beam search + Trie 查找的实际耗时是多少？
- **与传统信号的融合**：论文在 Limitation 中承认 RecGPT 还不能完全替代核心用户画像信号（user profile）。在实际系统中，RecGPT 更可能作为**召回/补充信号**，而非唯一的排序模型。

---

## 总结

RecGPT 是一个设计得很完整的系统，三个核心组件（FSQ token 化、混合注意力、Trie 解码）各自解决一个明确的问题。最让人印象深刻的是 **zero-shot 在 Amazon 子域上的巨大优势**——这说明推荐系统的基础模型路线是可行的。

但也要看到局限性：跨平台泛化仍然有限，冷启动场景的优势在宽松指标下不一定保持，工业部署细节不足。作为"第一个"通用顺序推荐基础模型，RecGPT 更多是一个方向的验证（proof of concept），而非终极解决方案。

---

**参考文献**：
- 论文：[arXiv:2506.06270](https://arxiv.org/abs/2506.06270)
- 代码：[https://github.com/HKUDS/RecGPT](https://github.com/HKUDS/RecGPT)
- FSQ 原始论文：[Finite Scalar Quantization: VQ-VAE Made Simple (arXiv:2309.15505)](https://arxiv.org/abs/2309.15505)
- MPNet：[MPNet: Masked and Permuted Pre-training for Language Understanding (NeurIPS 2020)](https://arxiv.org/abs/2004.09297)
- VQ-Rec：[Learning Vector-Quantized Item Representation for Transferable Sequential Recommenders (WWW 2023)](https://arxiv.org/abs/2210.12316)
- TIGER：[Recommender Systems with Generative Retrieval (NeurIPS 2023)](https://arxiv.org/abs/2305.05065)
