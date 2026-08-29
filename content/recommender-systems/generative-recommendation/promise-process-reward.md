---
title: "PROMISE：用过程奖励控制生成式推荐的 Semantic Drift"
date: 2026-08-29
tags:
  - 推荐系统
  - PROMISE
  - Process Reward Model
  - Test-Time Scaling
lang: zh
---

层级 SID 的生成是不可逆的。第一层选错粗语义分支后，后续 Token 即使都在局部最优，也只能在错误子树里继续搜索。这种错误累积被 [PROMISE](https://arxiv.org/abs/2601.04674) 称为 Semantic Drift。

## 结果奖励不够

普通 Reward Model 只评价完整 SID 或最终物品。它能告诉模型“最后错了”，却无法指出错误从哪一步开始。

Process Reward Model（PRM）对每个中间前缀进行评分：

$$
r_k=R(c_{1:k},H_u)
$$

如果第一层进入错误主题，PRM 可以立即降低这条路径的分数，而不必等完整 SID 生成完毕。

## PRM-guided Beam Search

Beam 排序不再只依赖 Token Log-probability，而是组合生成概率和过程奖励：

$$
S_k=\log P(c_{1:k}|H_u)+\lambda R(c_{1:k},H_u)
$$

这样能够更早剪掉语义漂移分支，把有限 Beam 预算留给更有希望的路径。

## Test-Time Scaling

增加 Beam、候选展开或验证计算，相当于在推理时投入更多算力。PROMISE 观察到，拥有 PRM 后，额外推理计算能较稳定地转化为质量提升，小模型甚至可能追上更大的基础生成模型。

## 工程权衡

PRM 必须足够轻，否则每扩展一个 Token 都调用复杂验证器会抵消收益。训练标签也决定上限：如果过程好坏无法从数据中可靠定义，PRM 只会引入另一层偏差。

PROMISE 的核心启发是：生成式推荐不能只优化最终答案。SID 具有明确的层级过程，中间步骤本身就是可以监督、搜索和分配计算的对象。
