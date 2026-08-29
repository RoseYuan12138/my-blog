---
title: "UniDot 与 FM Highway：为什么深度模型仍需要显式内积"
date: 2026-08-29
tags:
  - 推荐系统
  - UniDot
  - Feature Interaction
  - 序列建模
lang: zh
---

工业推荐长期存在两条模型路线：FM、DCN 等特征交互模型，以及 DIN、Transformer 等序列模型。生产系统通常先把序列压成向量，再与其他特征拼接，二者并没有真正统一。

[UniDot](https://arxiv.org/abs/2608.16797) 从一个简单观察出发：协同过滤的 Embedding 内积与 Attention 的 Query–Key 点积，本质上使用同一种计算原语。

## 两条并行总线

UniDot 把非序列特征和多域行为序列放进共享 Token 空间。每层包含：

- Token Mixing 路径，负责普通字段交互；
- Sequence Retrieval 路径，让候选 Token 读取行为序列；
- Fusion 模块，在两条路径之间交换信息。

序列只编码一次，供后续所有层复用，避免层数增加时重复支付序列编码成本。

## FM Highway

深层残差网络理论上可以学习二阶交叉，但浅层的强协同信号可能在多层变换中被稀释。FM Highway 在每层显式提取候选与不同序列、融合兴趣以及另一条总线 Token 的点积，并绕过深层融合器直达预测头。

可以把最终输入写成：

$$
h_{final}=[h_{deep};\phi_1;\phi_2;\ldots;\phi_L]
$$

$\phi_l$ 是第 $l$ 层产生的显式交互。使用拼接而非求和，保留了交互来自哪一层的信息。

## 为什么值得关注

更深的网络不代表低阶信号应该消失。推荐数据中用户—物品、候选—历史之间的二阶内积本来就是非常强的归纳偏置。显式旁路让模型同时拥有稳定的低阶记忆和高阶组合能力。

UniDot 的启发不是复古地回到 FM，而是承认：当一个简单运算与问题结构高度匹配时，应该让它成为架构的一部分，而不是等待深层网络偶然学会它。

## 参考资料

- [UniDot: A Unified Network for Sequence Modeling and Feature Interaction](https://arxiv.org/abs/2608.16797)
