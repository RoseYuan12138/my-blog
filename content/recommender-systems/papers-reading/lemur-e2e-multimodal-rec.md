---
title: "LEMUR / Cotrain：抖音搜索的端到端多模态推荐系统"
date: 2026-03-06
tags:
  - 推荐系统
  - 多模态
  - 端到端训练
  - 抖音
  - 字节跳动
lang: zh
english: recommender-systems/papers-reading/lemur-e2e-multimodal-rec.en
---

> 🌐 [Read in English](./lemur-e2e-multimodal-rec.en.md)

论文精读笔记：[LEMUR: Large scale End-to-end MUltimodal Recommendation](https://arxiv.org/abs/2511.10962)（ByteDance，2025）

> 内部名称 **Cotrain**，已上线抖音搜索和电商。

## 核心思路

工业界多模态推荐系统普遍是两阶段：先预训练 VLM，再冻结 Embedding 给 DLRM 用。这套框架的根本问题是 **VLM 无法感知真实用户反馈**——I2I 行为微调学到的是群体偏好，在"千人千面"的搜推场景里只能做到"千人一面"。

LEMUR / Cotrain 把多模态编码器和排序模型端到端联合训练，让 VLM 直接接收 DLRM 的反传信号，同时用 Memory Bank 解决序列计算瓶颈，是第一个在工业规模落地的端到端多模态推荐系统。

## 问题背景

字节跳动团队早在 **2022 年**就尝试过类似方向，但受限于当时推荐模型的计算能力和架构约束，未能成功上线。

随着抖音上 UGC 和长尾内容越来越多，传统 ID-based 系统的冷启动问题日益凸显——协同过滤依赖历史交互，新内容天然缺乏流量效率。多模态技术在搜推中的演进路径大致是：

> 视觉语言模型打 Tag → VLM Embedding 作为 DLRM 特征 → I2I 行为微调 VLM

然而，无论如何扩展微调数据或升级 VLM 规模，**两阶段训练范式**始终面临两个核心挑战：

**1. VLM 无法感知真实用户反馈**

I2I 微调（SwingI2I 等）本质上聚合的是群体偏好，未与下游 DLRM 联合训练。在"千人千面"场景下，仅依赖群体反馈的 VLM 学到的是"千人一面"的表示。

**2. 两阶段迭代链路复杂、效率低下**

数据准备 → 监督微调 → 模型上线 → 全量回溯 → 离线评估 → 部署上线，每次迭代都要走完这条链，维护成本高、迭代周期长。

两阶段的联合挑战还包括：每条用户序列有上百甚至上千个历史 item，实时对全序列跑 VLM 计算不可行；上万 batch size 下光传输图文数据就能打满 GPU 网络带宽。

## 系统架构

![LEMUR 整体架构：多模态编码、Memory Bank、序列建模、RankMixer 排序](./assets/lemur-architecture.png)

设计灵感来自**视觉自监督学习（SSL）中的 Memory Bank**——联合训练面临的"序列中成百上千 item 导致计算激增"，和对比学习中"构建海量负样本带来的计算开销"高度相似，两者的候选集也都来自历史正样本。

### 1. 多模态 Transformer 编码器

两个双向 Transformer 分别编码 query 和 document 的文本特征：

$$q_i = \text{Transformer}(q_\text{raw}^i), \quad d_i = \text{Transformer}(d_\text{raw}^i)$$

Document 文本涵盖：OCR 识别文字、ASR 语音转文字、视频标题、封面 OCR 文字。关键：Transformer **和 RankMixer 联合梯度更新**，不冻结。

### 2. SQDC：Session-masked Query-Document Contrastive

受 CLIP 启发，在 query 和 document 之间做对比学习。在搜索场景中，一个 batch 内可能有来自同一 query 的多个样本，高度相关但不应互为负例，因此引入 session-level mask：

$$\ell_\text{SQDC} = \sum_{i, \text{label}_i=1} -\log \frac{\exp(\text{sim}(q_i, d_i) \cdot T)}{\sum_{j} A_{ij} \cdot \exp(\text{sim}(q_i, d_j) \cdot T)}$$

$$A_{ij} = \begin{cases} 0 & i \neq j \text{ 且 } \text{QID}_i = \text{QID}_j \\ 1 & \text{其他} \end{cases}$$

**关键设计：False Negative 掩码。** 对于"曝光未点击但无负反馈"的样本，在 loss 中同样进行掩码处理，避免将真实的兴趣 item 误作负例——这充分利用了搜推业务特有的行为信号，比通用 VLM 表征学习更精准。

推荐场景中构建的是 Item-to-Item 任务，搜索场景是 Query-to-Item 任务（论文中称 SQDC = Session-masked Query-Document Contrastive）。

### 3. Memory Bank

![LEMUR 非对称部署：Memory Bank 支撑低延迟在线服务](./assets/lemur-memorybank-convergence.png)

这是解决序列计算瓶颈的核心设计。

**训练阶段（三步）：**
1. **去重分配**：针对搜推场景的头部效应，对当前候选视频池去重，均匀分配至各 GPU Rank
2. **VLM 推理 + All Gather**：每个 Rank 对分配的视频做 VLM forward，再 All Gather 同步到所有 Rank
3. **回写 Memory Bank**：最新 VLM Embedding 实时覆盖缓存

**推理阶段：**直接从 Memory Bank 读取，VLM 不参与实时推理。Online Learning 流式训练异步更新 Memory Bank。

**高热内容采样优化：** 由于头部效应，高热内容会被高频更新，而长尾内容的 Embedding 可能是数百 step 前的（Staleness 不均衡）。随着 VLM 逐步收敛，高热内容只以 **10% 概率参与 VLM 更新**，其余直接使用缓存值——节省约 **50% 的计算量**。

### 4. 多模态序列建模

![Decoder 结构：cross-attention 压缩序列](./assets/lemur-decoder.png)

历史序列 $\{d_1, \ldots, d_N\}$ 通过 Decoder（改自 LONGER）压缩：

$$Q_{i+1} = \text{FFN}\bigl(\text{CrossAttention}(Q_i, d_1, \ldots, d_N)\bigr)$$

另有 similarity module 计算目标 document 与历史序列的 cosine 相似度。最长序列 1000 条。

## 训练目标

主任务：二元交叉熵（CTR，正样本 = 观看超过 5 秒）：

$$\ell = \ell_\text{CTR} + \lambda \cdot \ell_\text{SQDC}$$

辅助 SQDC loss 直接给语义表示施加排序信号，防止 VLM 和 DLRM 的优化方向冲突。

## 实验结果

### 离线对比（抖音搜索，30 亿样本，70 天数据）

| 模型 | ΔQAUC vs 在线基线 |
|---|---|
| RankMixer | +0.59% |
| LONGER | +0.45% |
| LEMUR-SQDC | +0.47% |
| **LEMUR-SQDC-MB（完整）** | **+0.81%** |

工业场景下 0.1% QAUC 即可影响线上 A/B 结果。

### vs 两阶段方法

对比了基于两阶段用 Q2D（Query-to-Document）训练的 VLM（冻结后用于下游推荐），**LEMUR 端到端训练仍有显著优势**，说明即使 VLM 针对搜索任务微调，联合优化带来的收益依然不可替代。

### 线上 A/B 测试

- **抖音搜索**：14 天 A/B，query 改写率下降 **0.843%**，T-test 显著，已全量上线超过 1 个月
- **电商**：多个业务指标离线 + 在线均有收益，已上线

Cotrain 现已成为字节跳动**多模态 × 搜推的主流方向之一**。

### Staleness 与 Coverage

Memory Bank 有两个潜在问题：
- **Staleness**：缓存 Embedding 和当前模型输出的差距。实验显示相似度从 0.92 迅速上升到 0.945 后趋于稳定，总体影响不大
- **Staleness 不均衡**：高热内容几步前更新，长尾内容可能是几百步前的 Embedding。通过头部内容降采样（10% 更新概率）缓解，同时节省 50% 计算
- **Coverage**：当前 document > 98%，短序列 ~0.95，长序列 ~0.93，均超 90%

## 值得思考的点

1. **"千人一面" vs "千人千面"**：这个比喻非常精准。I2I 微调学到的是群体 co-click 信号，本质上是内容相似性而非个体偏好。联合训练让 VLM 直接从用户级别的 CTR 信号中学习，理论上能捕捉更细粒度的个性化——但目前 batch-level 的 CTR 信号依然是群体行为，真正的"千人千面"还需要更多工作。

2. **Memory Bank 的 Staleness 不均衡**：这个问题论文中有，但知乎文章讲得更清楚。高热内容频繁更新（embedding 新鲜），长尾内容几百步不更新（embedding 陈旧）。这不只是均值意义上的 staleness 问题，而是一个系统性偏差——模型在用新鲜 embedding 训练头部内容，用陈旧 embedding 训练长尾内容，长期可能导致头部表示过拟合。

3. **False Negative 掩码的重要性**：搜推场景里"曝光未点击"不等于负例——用户可能只是没滑到，或者感兴趣但没时间看。能利用业务信号（有无负反馈）来区分这类样本，是通用 VLM 对比学习框架做不到的，这是领域 know-how 的体现。

4. **VLM 当前用的是 SigLip（轻量级）**：未来计划升级到 Seed 1.6 36B 这类大参数模型，届时需要并行训练，对系统架构和资源调度要求更高。从轻量到大模型的跃迁是否会带来质变，还是边际收益递减？

5. **和 SARM 的路径对比**：SARM（快手）用 LLM 离线生成自然语言语义锚点，轻量编码，适合直播内容非平稳场景；Cotrain（字节）直接端到端训练文本 Transformer，适合大规模搜索/电商。两者都在解决"多模态和排序解耦"的问题，但底层哲学不同：SARM 是"先理解再排序"的改进版，Cotrain 是彻底打破两阶段边界。

## 未来工作（团队视角）

**性能方向：**
- 如何让用户序列中的重要 item 也参与 VLM 训练，扩大训练覆盖同时降低 Staleness？
- 更低侵入性地接入系统，避免 VLM 成为训练瓶颈，实现实验间多模态部分的高效复用
- 升级 VLM 到大参数量模型（如 Seed 1.6 36B），支持并行训练

**表征方向：**
- 突破对比学习为主的辅助 loss，引入 Grounding 等更丰富的监督信号
- 让 VLM 直接基于 CTR/CVR 等业务目标端到端获取梯度
- 设计更有效的机制缓解 Embedding Staleness，随 DLRM online learning 持续更新

## 参考

- [LEMUR: Large scale End-to-end MUltimodal Recommendation](https://arxiv.org/abs/2511.10962)（arXiv 2511.10962）
- LONGER（长序列建模，字节内部工作）
- MoCo / Memory Bank（视觉自监督学习先驱）
- Meta 搜推系统新范式（论文中引用 [3]）
