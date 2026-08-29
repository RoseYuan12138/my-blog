---
title: "推荐模型的 Scaling Law：为什么加参数经常没有用"
date: 2026-08-29
tags:
  - 推荐系统
  - Scaling Law
  - 大推荐模型
  - HSTU
lang: zh
---

语言模型扩大参数、数据和计算量后，Loss 往往呈可预测的幂律下降。推荐模型却经常出现另一种曲线：刚开始扩容有效，很快进入收益饱和区。

## 推荐为什么更难 Scaling

第一，大量参数位于 ID Embedding 表。增加表容量主要减少哈希碰撞、增强记忆，并不等价于增加通用计算能力。物品退出系统后，对应参数积累的知识也很难迁移。

第二，推荐数据不是稳定语料。用户、内容和曝光策略持续变化，训练分布由上一版模型共同决定。

第三，推荐输入同时包含稀疏 ID、稠密特征、行为序列和实时上下文。FLOPs 增加不代表 GPU 利用率增加，模型可能仍受通信或显存带宽限制。

## 怎样判断真正的 Scaling

应该把模型质量写成训练计算量 $C$ 的函数：

$$
L(C)=L_\infty + AC^{-\alpha}
$$

只有在多个数量级的计算范围内保持稳定趋势，才能用于预测更大模型的收益。如果只比较两个点，很容易把一次结构改进误称为 Scaling Law。

Meta 的 [HSTU](https://arxiv.org/abs/2402.17152) 将推荐重写为序列转导问题，并在多个计算规模上观察到幂律趋势。2026 年的 [Kunlun](https://arxiv.org/abs/2602.10016) 则把重点放在 Scaling Efficiency：模型不只要能变大，还要让新增计算真正转化为有效表示能力。

## 三个可扩展轴

- **Embedding Scaling**：扩大 ID 表和表示维度，增强记忆能力。
- **Dense Scaling**：增加网络宽度、深度和特征交互能力。
- **Sequence Scaling**：让模型看到更长、更丰富的用户行为。

三者必须平衡。如果 99% 参数都在 Embedding，而 Dense 网络极小，模型仍可能只是一个更大的记忆表。

## 工业意义

Scaling Law 的价值不是为“大模型”命名，而是减少昂贵试错：在训练前预测收益、选择模型规模、确定数据和算力应该投向哪里。

推荐模型真正的 Scaling，不是参数数字变大，而是每增加一单位计算，都能稳定换来更好的泛化和用户价值。

## 参考资料

- [Actions Speak Louder than Words: HSTU](https://arxiv.org/abs/2402.17152)
- [Kunlun: Establishing Scaling Laws for Massive-Scale Recommendation Systems](https://arxiv.org/abs/2602.10016)
