---
title: "Semantic ID：生成式推荐的词表"
date: 2026-08-29
tags:
  - 推荐系统
  - Semantic ID
  - 生成式推荐
  - Tokenization
lang: zh
---

生成式推荐首先要回答一个比模型结构更基础的问题：物品应该用什么 Token 表示？直接把每个 Item ID 当成独立词，词表会持续增长，新物品没有语义邻居，模型也无法共享知识。

Semantic ID（SID）把一个物品表示为短 Token 序列：

$$
i\rightarrow (c_1,c_2,\ldots,c_m)
$$

每个 $c_k$ 来自有限码本。语义相近的物品会共享部分前缀或码字，模型因此可以把一个物品上学到的规律迁移到相似物品。

## SID 带来的三种能力

**有限词表**：Item 数量可以持续增长，模型输出空间仍由有限码本组成。

**层级语义**：前层码字描述粗类别，后层码字补充细节。生成过程天然形成从粗到细的决策树。

**冷启动泛化**：新物品只要拥有内容表示，就能被量化到已有语义空间，不必等待大量交互才能获得有效表示。

## SID 不是纯内容标签

只用图像或文本聚类，得到的是内容分类，不一定适合推荐。两个内容相似的物品可能服务不同人群；两个视觉差异很大的物品也可能被同一群用户连续消费。

因此工业 SID 常融合：

- 多模态内容语义；
- Item–Item 协同关系；
- 业务价值和行为目标；
- 防碰撞与容量约束。

## 与 ID Embedding 的关系

SID 擅长泛化，普通 ID 擅长精准记忆。很多系统不会立刻删除 ID，而是采用 Hybrid Tokenization：语义 Token 提供共享结构，ID 或残差 Token 记录无法被语义解释的个体差异。

## 最重要的判断

生成模型的上限很大程度由 Tokenizer 决定。模型再强，如果两个完全不同的物品被量化到同一 SID，它就无法在解码阶段把它们分开；如果 SID 近似随机 ID，生成模型又失去语义共享价值。

Semantic ID 的本质，是为推荐系统设计一套既能表达语义、又能承载协同信号的“语言”。

## 参考资料

- [Better Generalization with Semantic IDs](https://arxiv.org/abs/2306.08121)
- [Recommender Systems with Generative Retrieval](https://arxiv.org/abs/2305.05065)
