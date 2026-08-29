---
title: "Kunlun：推荐 Scaling Law 背后的效率架构"
date: 2026-08-29
tags:
  - 推荐系统
  - Kunlun
  - Scaling Law
  - Meta
lang: zh
---

[Kunlun](https://arxiv.org/abs/2602.10016) 的重点不是简单提出一个更大的推荐网络，而是回答：同时包含行为序列和非序列上下文时，如何让模型质量随计算量稳定 Scaling？

## 问题：计算投进去，模型却吃不下

传统工业推荐模型混合了大量异构模块。部分模块 MFU 很低，部分特征又获得了过多计算，导致新增 FLOPs 无法稳定转化为质量收益。

Kunlun 把改进分为底层算子效率和高层计算分配。

## 底层模块

**Generalized Dot-Product Attention（GDPA）**统一多种交互形式，使序列和非序列特征能使用更规整的点积计算。

**Hierarchical Seed Pooling（HSP）**用一组层级 Seed 对长序列进行摘要，在保留多兴趣的同时控制 Token 数。

**Sliding Window Attention**让局部事件进行细粒度交互，避免所有 Token 都承担全局二次复杂度。

## 高层计算重分配

**Computation Skip**根据输入和层状态跳过价值较低的计算，不要求每个请求、每个 Token 都经过完全相同的路径。

**Event-level Personalization**把计算聚焦到更重要的用户事件，而不是平均分给所有历史行为。

其核心不是“稀疏就是好”，而是让计算分配随输入价值变化。

## 结果意味着什么

论文报告在 NVIDIA B200 上将 MFU 从 17% 提升到 37%，并提高 Scaling Efficiency。更重要的是，架构在序列和上下文特征共同存在时仍呈现可预测 Scaling。

## 我的理解

Kunlun 给推荐大模型一个重要提醒：Scaling Law 不是纯统计现象，而是架构、优化器、硬件利用和计算路由共同塑造的结果。如果模型本身低效，观测不到 Scaling 并不能证明数据里没有规律，只能说明计算没有以正确方式到达数据。

## 参考资料

- [Kunlun: Establishing Scaling Laws for Massive-Scale Recommendation Systems through Unified Architecture Design](https://arxiv.org/abs/2602.10016)
