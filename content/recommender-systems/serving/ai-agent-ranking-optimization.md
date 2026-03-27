---
title: "Sortify：当 AI Agent 接管推荐系统的排序优化"
date: 2026-03-26
tags:
  - 推荐系统
  - AI Agent
  - LLM
  - 排序优化
  - Sortify
lang: zh
english: recommender-systems/serving/ai-agent-ranking-optimization.en.md
---

> 🌐 Read in English (coming soon)

推荐系统的排序优化一直是个"人力密集型"工作——调参、上线、看数据、再调参。[Sortify](https://github.com/yinsn/sortify-resources) 做了一件激进的事：让 LLM 驱动的自治 Agent 完全接管这个循环，7×24 自主运行，零人工干预。

这篇笔记整理 Sortify 的核心设计思路，重点看它如何用决策理论解决排序优化中的结构性问题。

## 传统排序优化的三个老问题

做过 [[recommender-systems/index|推荐系统]] 排序优化的人大概都踩过这些坑：

**1. 离线-在线鸿沟**

离线优化的参数上线后表现不符预期。更麻烦的是，不同指标的偏差方向不一致——有些过度乐观，有些过度悲观。你没法用一个全局校准因子同时修正所有指标。

**2. 诊断纠缠**

指标不好的时候，两种可能：
- 世界模型错了（离线预测没反映在线现实）
- 目标权重错了（约束惩罚不够严格）

这两种错误需要**相反方向**的修正，但产生的症状可能完全一样。人工靠经验猜，效率很低。

**3. 轮次间无学习**

每轮优化从头开始。上一轮好不容易摸索出的校准规律，下一轮全丢了。每天都是 Groundhog Day。

## Sortify 的核心思路：信念与偏好分离

Sortify 的理论基础是 [Savage 的主观期望效用（SEU）理论](https://en.wikipedia.org/wiki/Subjective_expected_utility)。核心主张：

> **把"对世界的信念"和"对结果的偏好"强制分离到两个独立通道。**

这不是工程上的随意拆分，而是决策理论的基本公理——信念（Belief）描述"世界是什么样"，偏好（Preference）描述"我想要什么"。混在一起优化，就是诊断纠缠的根源。

## 三层架构

| 层级 | 职责 | 更新频率 |
|-----|------|---------|
| **L1: 人类/配置** | 业务目标、约束边界、初始参数 | 低频（人工设定） |
| **L2: LLM + 算法** | 信念校准 + 偏好适应 | 每轮自动（双通道） |
| **L3: Optuna TPE 搜索** | 在校准后的空间内搜索最优 7 维参数 | 5000 trials × 25 workers |

人类只管 L1（定方向），LLM 管 L2（调校准），数值优化器管 L3（搜参数）。各层职责清晰，不互相越界。

## 核心机制

### 影响力分解（Influence Share）

Sortify 引入了一个新指标：**Influence Share**，把排序决策分解为各因素的百分比贡献。

它满足四个性质：
- **可分解**：每个因素的精确贡献可测量
- **可求和**：所有份额加起来 = 100%
- **单调性**：增加某因素的权重 → 该因素份额增加
- **可操作**：可以做精确的权衡推理，比如"从订单数转移 5% 影响力到 GMV"

这让排序调优从"调个参数看看效果"变成了"精确分配各因素的决策影响力"。

### 双通道机制（几何正交）

这是 Sortify 最精巧的设计。两个校准通道在几何上正交，互不干扰：

**Belief 通道（信念校准）**
- 解决的问题：离线指标如何映射到在线现实？
- 控制变量：`target_range`（约束边界的位置）
- 更新方式：LMS 回归 + LLM 截距跳跃
- 错误类型：认知性错误——你的地图和地形不匹配
- 几何含义：**水平移动**约束边界

**Preference 通道（偏好校准）**
- 解决的问题：约束违反应该被多严重地惩罚？
- 控制变量：`penalty_weight`（约束边界的硬度）
- 更新方式：非对称乘法缩放
- 错误类型：公理性错误——你对"绕路"的在乎程度不对
- 几何含义：**垂直缩放**违反成本

两通道几何正交的好处：Belief 通道的修正不影响 Preference 通道，反之亦然。这从根本上解决了诊断纠缠问题。

### LLM 元控制器

LLM **从不直接调底层的 7 维参数**。它只操作两个高级旋钮：

```text
delta_intercept  ∈ [-0.1, +0.1]   # 微调离线→在线映射（Belief 通道）
penalty_multiplier ∈ [0.5, 2.0]   # 缩放约束严格度（Preference 通道）
```

LLM 从结构化上下文中推理——过去 20 个 episode 的完整记录 + 30 次校准更新的历史。输出是带有强制证据引用的 JSON 提案。

关键安全设计：**低信心时返回空提案**。不确定就不动，比瞎调强。

### 持久内存（7 表 SQLite）

Sortify 用 SQLite 维护 7 张表的跨轮次记忆：

```sql
episodes                      -- 完整的离线/在线配对记录
prior_relations               -- 当前迁移斜率和截距（6 个指标）
prior_update_history          -- 所有信念更新（LMS + LLM），30 条窗口
penalty_weights               -- 当前约束惩罚值
penalty_weight_update_history -- 偏好通道更新，30 条窗口
llm_proposals                 -- LLM 推荐及证据引用
evidence_links                -- 提案与 episodes 的可追溯性
```

每轮不再从零开始，而是继承并构建在所有先前学习之上。Groundhog Day 问题消失了。

## 运行模式：三状态机

```text
Coldstart → Initial → YOLO
```

- **Coldstart**：启动初始参数，锚定时间窗口
- **Initial**：执行完整管道一次，可选人工确认
- **YOLO**：无限自主循环

YOLO 模式下，每个周期约 4 小时（3.5h 等数据 + 25-50min 处理），执行 10 步管道：

$$
\text{拉 A/B 数据} \to \text{记录} \to \text{LMS 校准} \to \text{LLM 上下文} \to \text{LLM 提案} \to \text{应用更新} \to \text{推导目标} \to \text{更新惩罚} \to \text{Optuna 搜索} \to \text{发布 Redis}
$$

每天约 6 轮，发布后零人工干预。

## 实验结果

**Market A（热启动，已有历史数据）**

| 指标 | 变化 |
|-----|------|
| GMV | 从 -3.6% 逆转到 +9.2%（7 轮） |
| Orders | 峰值 +12.5% |

**Market B（冷启动，全新市场）**

| 指标 | 7 天 A/B 结果 |
|-----|-------------|
| GMV/UU | +4.15% |
| 广告收入 | +3.58% |

**自主性指标**
- 最长连续自主运行：25 小时（7 轮）
- LLM 每轮纠正数从 5 个收敛到 2 个
- 每轮 LLM 成本：$0.03–$0.10

## 一个有意思的事实

整个 Sortify 系统——98,000 行代码、78 个模块、7 个子系统——**零行代码由人类手写**。全部由 AI coding agents 生成，单人编排。系统基于 [ParaDance](https://pypi.org/project/paradance/)（101K+ PyPI 下载）构建。

这本身就是一个 AI Agent 能力的证明：不仅能运行排序优化，连优化系统本身都是 Agent 写的。

## 启示

Sortify 的设计有几个值得借鉴的点：

1. **决策理论不是摆设**。Savage SEU 理论在这里不是装饰性引用，而是直接指导了架构设计——Belief/Preference 分离解决了实际的诊断纠缠问题。

2. **LLM 不该直接调参数**。让 LLM 操作高层语义旋钮（校准截距、惩罚系数），而不是底层数值参数，是更合理的人机分工。

3. **记忆是自主性的基础**。没有跨轮次记忆，Agent 每轮都在重复发现同样的规律。7 表 SQLite 看起来简单，但它是 YOLO 模式能持续运行的关键。

4. **安全靠设计，不靠祈祷**。低信心返回空提案、双通道正交、有界的调节范围——这些约束让 Agent 在"不确定"时默认安全。

---

**参考资源**
- [Sortify 项目主页](https://github.com/yinsn/sortify-resources)
- [技术报告（中文 PDF）](https://github.com/yinsn/sortify-resources/blob/main/docs/Sortify-Technical-Report-zh.pdf)
- [设计文档（中文）](https://github.com/yinsn/sortify-resources/blob/main/docs/design/zh)
- [知乎博客文章](https://github.com/yinsn/sortify-resources/blob/main/blog/zhihu_post.md)
- [Demo 视频](https://github.com/yinsn/sortify-resources/blob/main/docs/sortify-demo.mp4)
- [ParaDance (PyPI)](https://pypi.org/project/paradance/)
- [Savage 主观期望效用理论 (Wikipedia)](https://en.wikipedia.org/wiki/Subjective_expected_utility)
