---
title: "OneRec：从生成式召回走向统一召回与排序"
date: 2026-08-29
tags:
  - 推荐系统
  - OneRec
  - 生成式推荐
  - DPO
lang: zh
---

早期生成式推荐通常只替代召回，后面仍接传统排序模型。[OneRec](https://arxiv.org/abs/2502.18965) 更激进：用一个生成模型直接产生推荐 Session，试图统一召回和排序。

## Session-wise Generation

普通 Next-Item Prediction 一次只预测一个物品，线上还要依赖规则把单点结果组合成列表。OneRec 直接生成一组连续物品，让模型学习列表内部的上下文与顺序。

模型采用 Encoder–Decoder：Encoder 编码用户行为，Decoder 自回归产生物品 Token。Sparse MoE 用于扩大模型容量而不线性增加每次推理 FLOPs。

## Iterative Preference Alignment

最大似然训练倾向于复现历史数据，却不保证生成列表符合当前策略目标。OneRec 使用 Reward Model 模拟用户反馈，再构造偏好对进行 DPO：

$$
L_{DPO}=-\log\sigma\left(\beta\log\frac{\pi(y^+|x)}{\pi_{ref}(y^+|x)}-
\beta\log\frac{\pi(y^-|x)}{\pi_{ref}(y^-|x)}\right)
$$

它让模型提高高奖励列表的概率，同时避免策略偏离基线过远。

## 真正统一的难点

统一模型消除了阶段目标错位，但引入新的问题：列表生成延迟、Beam 多样性、重复物品、非法 SID、Reward Model 偏差，以及生成策略发生变化后的 Off-policy 数据。

因此“统一”并不意味着没有索引和规则，而是把核心决策目标放进同一个可训练模型，工程约束继续作为解码和 Serving 系统存在。

## 这条路线的意义

OneRec 将生成式推荐从一种新召回器，推进为完整决策模型。它也为后续 OneRec-Think 和 OneReason 提供了基础：只有推荐结果本身已经是一种可生成语言，才有可能在生成过程中插入偏好解释和推理过程。
