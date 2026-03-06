---
title: "SARM：用 LLM 语义锚点做端到端直播排序"
date: 2026-03-06
tags:
  - 推荐系统
  - 直播推荐
  - LLM
  - 多模态
  - 排序模型
lang: zh
english: recommender-systems/models/sarm-llm-livestream-ranking.en
---

> 🌐 [Read in English](./sarm-llm-livestream-ranking.en.md)

论文精读笔记：[SARM: LLM-Augmented Semantic Anchor for End-to-End Live-Streaming Ranking](https://arxiv.org/abs/2602.09401)（快手，2026）

## 核心思路

直播推荐的难点在于：主播内容是实时变化的多模态信号（画面、声音、弹幕），传统 ID-based 特征和离散标签捕捉不到这些语义。SARM 的做法是用 MLLM（多模态大语言模型）给每个直播间生成**自然语言描述**作为"语义锚点"，然后把这些文本表示**端到端地接入排序模型**一起训练，让语义理解直接服务于排序目标。

和之前方案的区别：
- **聚类标签（SID）**：把主播聚成几百个类别，粗粒度，信息损失大
- **冻结 MLLM embedding**：embedding 不参与排序训练，和排序目标不对齐
- **SARM**：可学习的文本 token 作为语义锚点，跟着排序 loss 一起优化

## 系统架构

整个系统分三层：

```
MLLM 离线生成语义锚点（6 维度文本描述）
         ↓
Semantic Anchor Encoder（SAE）编码文本
         ↓
接入 MMoE 排序模型，端到端联合训练
```

### 语义锚点生成（离线）

用 Qwen2.5-VL / Qwen3-VL 对每个直播间生成 6 个维度的自然语言描述：

| 维度 | 说明 | 示例 |
|---|---|---|
| Point of Interest | 核心吸引点 | "歌手现场演唱流行歌曲" |
| Theme | 主题分类 | "音乐表演" |
| Topic | 细分话题 | "华语流行、翻唱" |
| Target Audience | 目标受众 | "喜欢轻松音乐的年轻用户" |
| Format | 内容形式 | "单人直播、实时互动" |
| Scene | 场景描述 | "室内、暖色灯光、专业麦克风" |

每天离线跑一次，更新所有活跃主播的锚点。

### Semantic Anchor Encoder（SAE）

一个轻量的 4 层 BERT-style Transformer：
- 单头 attention + RoPE 位置编码
- 输入是语义锚点文本的 token 序列

关键设计在 tokenizer 和融合机制上。

#### 直播领域 Tokenizer

标准 LLM tokenizer 会把直播领域的高频术语拆成碎片（比如"连麦PK"可能被拆成多个 subword）。SARM 用迭代 BPE 扩展 tokenizer：

1. 统计语义锚点语料中的高频词组
2. 出现 ≥100K 次的合并成原子单元
3. 保留原始 tokenizer 的通用词表不动

这样"连麦PK"、"才艺展示"这类领域术语变成单个 token，编码更紧凑。

#### Gated Fusion 机制

有了领域 token 后，怎么和通用 token 融合？直接拼接会让通用语义能力退化。SARM 用门控注入：

设 $h_i$ 是基础 tokenizer 的第 $i$ 个 token embedding，$e'_i$ 是对应的领域 token embedding：

$$k_i = W_K e'_i, \quad v_i = W_V e'_i$$

$$\alpha_i = \sigma\left(\frac{\text{RMSNorm}(h_i)^T \cdot \text{RMSNorm}(k_i)}{\sqrt{d}}\right)$$

$$h'_i = h_i + \alpha_i \cdot v_i$$

门控值 $\alpha_i$ 通过 attention score 决定注入多少领域语义。当领域 token 和基础 token 语义匹配度高时，$\alpha_i$ 大，注入多；不匹配时趋近 0，保留原始表示。

### 主播侧表示

SAE 输出两个向量：

**[CLS] 表示** $h_{\text{CLS}}$：语义锚点的全局语义向量，捕捉直播内容特征。

$$h_{\text{CLS}} = \text{SAE}(\text{tokens})_{\text{[CLS]}}$$

**[TAR] 表示** $h_{\text{TAR}}$：身份感知的语义向量。用一个可学习的 author ID embedding $q_a$ 对 SAE 输出做 cross-attention：

$$h_{\text{TAR}} = \text{CrossAttn}(q_a, H_{\text{SAE}})$$

直觉上，同一类内容（比如"户外钓鱼"）的不同主播，[CLS] 很相似，但 [TAR] 会因为各自的 ID embedding 不同而产生差异化表示，捕捉"同类但不同人"的个性化信号。

### 用户侧表示

用户兴趣 $h_{\text{UIN}}$ 通过历史观看记录构建：

1. 从 Memory Bank 检索用户看过的主播的 $h_{\text{CLS}}$ 向量序列
2. 过一层 Transformer 建模序列关系
3. Mean Pooling 得到用户兴趣表示

$$H_{\text{seq}} = \text{Transformer}([h_{\text{CLS}}^{a_1}, h_{\text{CLS}}^{a_2}, ..., h_{\text{CLS}}^{a_n}])$$

$$h_{\text{UIN}} = \text{MeanPooling}(H_{\text{seq}})$$

### Memory Bank

维护一个以 author ID 为索引的缓存：

$$M[a] = (h_{\text{CLS}}^a, h_{\text{TAR}}^a)$$

训练时实时更新，推理时直接查表，不需要重新编码。

### 排序模型集成

把 $h_{\text{CLS}}$、$h_{\text{TAR}}$、$h_{\text{UIN}}$ 和传统排序特征拼接，送入 MMoE 多任务模型，同时预测 CTR、WTR（watch time rate）、LVTR（long view）、GTR（gift rate）。

## 训练目标

### 主任务：推荐 Loss

四个任务共享 MMoE 底层，各自有独立 tower：

$$\mathcal{L}_{\text{rec}} = -\sum \left[ y_{\text{xtr}} \log \hat{y}_{\text{xtr}} + (1 - y_{\text{xtr}}) \log(1 - \hat{y}_{\text{xtr}}) \right]$$

其中 xtr ∈ {CTR, WTR, LVTR, GTR}。

### 辅助任务：语义监督

单独用 $h_{\text{CLS}}$ 和 $h_{\text{TAR}}$ 做一个轻量预测头，提供额外的监督信号：

$$\hat{y}_{\text{aux}} = \text{MLP}(\text{Concat}[h_{\text{CLS}}^a, h_{\text{TAR}}^a])$$

$$\mathcal{L}_{\text{aux}} = -y \log \hat{y}_{\text{aux}} - (1-y) \log(1 - \hat{y}_{\text{aux}})$$

### 总 Loss

$$\mathcal{L} = \mathcal{L}_{\text{rec}} + \lambda \mathcal{L}_{\text{aux}}$$

辅助任务的意义：语义表示通过排序主任务的梯度更新时，信号要经过 MMoE 和多层 tower 传回来，路径长，容易梯度稀疏。辅助任务给语义表示提供更直接的密集监督，稳定训练。

## 非对称部署策略

这是让系统在生产环境跑起来的关键设计：

| | 主播侧（重，离线） | 用户侧（轻，在线） |
|---|---|---|
| MLLM 推理 | 每天离线跑一次 | 不涉及 |
| SAE 编码 | 离线编码，存入 Memory Bank | 在线从 Memory Bank 查表 |
| 推理延迟 | 不影响在线 | 常数时间查表 |
| 更新频率 | 每日 | 实时（streaming 连续训练） |

主播侧的重计算（MLLM + SAE）全部离线完成，在线推理只需要从 Memory Bank 按 author ID 查向量，是 O(1) 操作。用户侧的 Transformer 编码和训练时一致，不引入 train-serve skew。

## 实验结果

### 离线指标（Base Model: HoME）

逐步加组件的 ablation：

| 方法 | CTR AUC | CTR GAUC | WTR AUC | WTR GAUC | LVTR AUC | LVTR GAUC | GTR AUC | GTR GAUC |
|---|---|---|---|---|---|---|---|---|
| Base | 0.8387 | 0.6453 | 0.9217 | 0.6500 | 0.8928 | 0.7542 | 0.9792 | 0.7319 |
| + Tags | 0.8390 | 0.6457 | 0.9220 | 0.6510 | 0.8932 | 0.7542 | 0.9794 | 0.7324 |
| + SIDs | 0.8389 | 0.6469 | 0.9221 | 0.6536 | 0.8936 | 0.7553 | 0.9799 | 0.7324 |
| + MLLM Emb (MMBee) | 0.8385 | 0.6451 | 0.9210 | 0.6475 | 0.8932 | 0.7551 | 0.9790 | 0.7320 |
| + MLLM Emb (SIM) | 0.8394 | 0.6463 | 0.9224 | 0.6509 | 0.8939 | 0.7548 | 0.9792 | 0.7330 |
| + SAE (Author) | 0.8396 | 0.6475 | 0.9225 | 0.6511 | 0.8948 | 0.7567 | 0.9804 | 0.7342 |
| + Aux Loss | 0.8398 | 0.6474 | 0.9227 | 0.6513 | 0.8948 | 0.7573 | 0.9803 | 0.7352 |
| + User Sequence | 0.8405 | 0.6483 | 0.9227 | 0.6519 | 0.8955 | 0.7575 | 0.9816 | 0.7358 |
| **SARM (Full)** | **0.8411** | **0.6485** | **0.9232** | **0.6522** | **0.8959** | **0.7580** | **0.9825** | **0.7369** |

相比 Base 的提升：CTR AUC +0.29%，CTR GAUC +0.50%，LVTR AUC +0.35%，GTR AUC +0.34%。

几个值得注意的点：
- **冻结 MLLM embedding（MMBee）甚至比 Base 还差**，验证了"不参与排序训练的语义表示没用"这一论点
- **SIDs 在 GAUC 上比 Tags 好**，说明聚类 ID 比稀疏标签对个性化排序更有用
- **Aux Loss 主要提升 GTR（+0.28% GAUC）**，打赏是更稀疏的信号，辅助监督帮助更大

### Gated Fusion Ablation

| [CLS] 编码方式 | CTR AUC Δ | CTR GAUC Δ | LVTR AUC Δ | LVTR GAUC Δ |
|---|---|---|---|---|
| Base Tokenizer | +0.07% | +0.10% | +0.10% | +0.08% |
| Live-Streaming Tokenizer only | +0.06% | +0.06% | +0.08% | +0.06% |
| **Gated Fusion** | **+0.09%** | **+0.14%** | **+0.12%** | **+0.22%** |

单用领域 tokenizer 反而不如基础 tokenizer（通用语义能力受损），门控融合两者兼得。

### [TAR] 身份感知表示 Ablation

| 聚合方式 | CTR AUC Δ | CTR GAUC Δ | LVTR AUC Δ | LVTR GAUC Δ |
|---|---|---|---|---|
| Mean Pooling | +0.04% | +0.07% | +0.10% | +0.13% |
| **Cross-Attention** | **+0.09%** | — | **+0.22%** | **+0.25%** |

Cross-Attention 在 LVTR（长时间观看）和 GAUC 上提升明显，说明身份感知对个性化长期留存更重要。

### 用户序列表示 Ablation

| 用什么向量建序列 | CTR AUC Δ | LVTR AUC Δ |
|---|---|---|
| [TAR] sequence | +0.15% | +0.28% |
| **[CLS] sequence** | **+0.18%** | **+0.30%** |

用 [CLS]（内容语义）而不是 [TAR]（身份语义）来建用户兴趣序列效果更好——用户兴趣更多由内容类型驱动，而非特定主播身份。

### 长尾主播分析

按曝光量分桶：[0-60), [60-100), [100-1K), [1K-10K), [10K-∞)。SARM 在低曝光主播上 GAUC 提升最大。这符合直觉：热门主播已有充足的行为数据，ID 特征就够用；长尾主播行为稀疏，语义锚点的内容理解能力帮助更大。

### 在线 A/B 实验（快手 + 快手极速版，2 周）

| 平台 | 曝光 | 观看次数 | 观看时长 | 点击 | 打赏 | 有效观看 | 关注 |
|---|---|---|---|---|---|---|---|
| 快手 | +0.424% | +0.189% | +0.092% | +0.982% | +0.482% | +0.070% | +0.805% |
| 快手极速版 | +1.190% | +0.397% | +0.962% | +0.562% | +1.287% | +0.340% | +0.522% |

极速版涨幅更大，可能因为极速版用户群更依赖推荐（相比主站用户有更多主动搜索和关注行为）。

### MLLM 质量敏感性

| MLLM | 综合分 | CTR AUC Δ | CTR GAUC Δ | LVTR AUC Δ | LVTR GAUC Δ |
|---|---|---|---|---|---|
| Qwen2.5-VL-7B | 2.308 | +0.19% | +0.20% | +0.27% | +0.22% |
| **Qwen3-VL-8B** | 2.519 | **+0.24%** | **+0.32%** | **+0.31%** | **+0.38%** |

更好的 MLLM → 更好的语义锚点 → 更好的排序效果。架构不变，换更强的 MLLM 就能直接收益。

### 计算开销

| 资源 | 训练开销增加 | 推理 QPS 下降 | 单请求延迟增加 |
|---|---|---|---|
| CPU | +3.02% | -3.4% | +2% |
| GPU | +2.75% | — | — |

开销可以忽略不计，适合生产部署。

## Attention 可视化

论文的 Figure 7 展示了 [CLS] token 对不同词的 attention 权重。对于美妆主播，高权重词集中在"颜值"、"护肤"、"互动"；对于音乐主播，集中在"歌手"、"演唱"、"氛围"。说明语义锚点确实学到了有区分度的内容理解，而不是所有主播都趋同。

## 值得思考的点

1. **语义锚点的 6 个维度是手工设计的**——如果维度选得不好，信息覆盖不全怎么办？论文没讨论维度选择的敏感性。
2. **每天离线更新一次锚点**——对于内容快速变化的直播场景（比如主播中途换话题），日级更新是否够？能否做增量更新？
3. **Gated Fusion 本质上是一个 side information injection**——这个思路不限于直播，任何有丰富 side information 但又不想破坏主模型表示空间的场景都可以借鉴。
4. **辅助 loss 的设计很巧妙**——给中间表示加直接监督信号来解决长路径梯度稀疏问题，这在深模型训练里是通用技巧。
5. **"更好的 MLLM = 更好的排序"** 这个结论意味着 SARM 的天花板取决于 MLLM 能力——随着 MLLM 进步，排序模型也会自动受益，这是个好的架构特性。

## 参考

- [SARM: LLM-Augmented Semantic Anchor for End-to-End Live-Streaming Ranking](https://arxiv.org/abs/2602.09401)
- [Qwen2.5-VL](https://arxiv.org/abs/2412.14135)
- [MMoE: Modeling Task Relationships in Multi-Task Learning](https://dl.acm.org/doi/10.1145/3219819.3220007)
