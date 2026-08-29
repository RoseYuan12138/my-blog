---
title: "TIGER：把推荐检索改写为生成 Semantic ID"
date: 2026-08-29
tags:
  - 推荐系统
  - TIGER
  - 生成式检索
  - Semantic ID
lang: zh
---

[TIGER](https://arxiv.org/abs/2305.05065) 是生成式推荐的重要起点。传统双塔先生成用户向量，再通过 ANN 搜索相近物品；TIGER 让 Transformer 直接生成目标物品的 Semantic ID。

## 两阶段流程

第一阶段使用物品内容特征和 Residual Quantization，为每个物品构造多层 SID。

第二阶段把用户交互历史写成 SID 序列，用 Encoder–Decoder Transformer 预测下一个物品的 SID：

$$
P(c_1,\ldots,c_m\mid H_u)=\prod_{k=1}^{m}P(c_k\mid c_{<k},H_u)
$$

推理时通过 Beam Search 生成多个合法 SID，再映射回候选物品。

## 相比双塔改变了什么

双塔把检索约束为一个向量空间中的近邻搜索；TIGER 通过自回归条件概率表达层级决策，理论上可以建模更复杂的多峰兴趣。

SID 的共享前缀还让新物品继承相似内容的统计能力，这也是论文在冷启动场景中表现突出的原因。

## 仍未解决的问题

- Tokenizer 与推荐模型分阶段训练，SID 未必为推荐目标最优。
- Beam Search 的早期错误会把后续生成带入错误子树。
- 一个 SID 对应多个物品时，需要额外排序或消歧。
- 物品库更新后，Trie 和模型词表必须保持一致。

## 为什么 TIGER 仍值得读

后续工作虽然加入动态 Tokenizer、偏好对齐、Decoder-Only 和强化学习，但核心骨架依然存在：把物品离散化，把用户历史视作 Token 序列，再用约束生成完成检索。

TIGER 最重要的贡献，是把“推荐系统必须输出一个向量”改成了“推荐系统也可以生成一种离散语言”。
