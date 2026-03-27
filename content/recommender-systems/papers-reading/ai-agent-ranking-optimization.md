---
title: "Sortify：AI Agent 重新定义推荐系统排序优化"
date: 2026-03-26
tags:
  - 推荐系统
  - AI Agent
  - LLM
  - 排序优化
  - 双通道机制
  - 持久内存
lang: zh
english: recommender-systems/papers-reading/ai-agent-ranking-optimization.en.md
---

> 🌐 Read in English (coming soon)

推荐系统的排序优化一直是个"人力密集型"工作——调参、上线、看数据、再调参。一个资深工程师的日常可能是这样的：早上看昨晚 A/B 实验的数据，发现 GMV 涨了但订单量跌了，花两小时分析原因，调几个权重，提交新实验，然后等到第二天再看。一周能迭代 3-4 次就算快了。

[Sortify](https://github.com/yinsn/sortify-resources) 做了一件激进的事：让 LLM 驱动的自治 Agent 完全接管这个循环，每 4 小时自动迭代一次，7×24 自主运行，零人工干预。更激进的是，整个系统 98,000 行代码全部由 AI coding agents 生成。

这篇笔记深入拆解 Sortify 的每一个核心机制——不只是"做了什么"，而是"怎么做的"和"为什么这样做"。

---

## 1. 离线-在线鸿沟：到底有多离谱？

做过 [[recommender-systems/index|推荐系统]] 排序优化的人都知道离线指标不可全信。但 Sortify 团队遇到的情况比"不可全信"严重得多——**离线和在线可以完全反向**。

### 一个真实的例子

假设你在离线环境调好了一组排序参数，离线评估说：

```
离线预测：
  GMV:     +18.2%  ✓ 看起来很棒
  Orders:  +12.5%  ✓ 也不错
  Ads Rev: +5.2%   ✓ 平稳
```

你很兴奋，上线了。三天后看数据：

```
在线实际：
  GMV:     -3.6%   😱 反向了！
  Orders:  +8.3%   🤔 居然比预测低？
  Ads Rev: +5.1%   ✓ 倒是挺准
```

GMV 的离线预测和在线现实差了 21.8 个百分点，而且方向相反。

### 为什么不同指标的偏差方向不同？

这里有个微妙的问题：**不是所有指标都朝同一个方向偏**。你没法用一个全局校准因子来修正。

**GMV 过度乐观**的原因：
- 离线数据没有捕捉到用户的价格敏感性——在离线日志里，用户看到了商品并购买，但在线环境中排序变了，高价商品被推到更显眼的位置，用户看了但没买
- 竞对平台的流量分散效应——离线数据是历史快照，没有反映用户在多个平台间的切换行为
- 曝光偏差（exposure bias）：离线评估假设用户会看到所有推荐结果，实际上用户只看前几个

**Orders 过度悲观**的原因：
- 模型低估了**曝光本身对转化的拉动效应**——一个商品排到第 3 位和第 30 位，转化率差距可能是 10 倍
- 离线评估时用的是静态的 CTR/CVR 模型，没有考虑到新排序带来的"注意力重分配"

**广告收入反而准确**的原因：
- 广告模型本身就是用在线反馈直接优化的（eCPM 竞价），它的离线预测自带在线校准
- 广告收入主要受 eCPM 和展示量驱动，这两个变量的离线估计相对稳定

关键洞察：**偏差不是噪声，是结构性的**。每个指标有自己的偏差模式，需要独立校准。

---

## 2. 理论基础：Savage 的 SEU 理论

Sortify 的理论基础是 [Savage 的主观期望效用（SEU）理论](https://en.wikipedia.org/wiki/Subjective_expected_utility)。这不是装饰性引用——整个系统架构直接由这个理论推导出来。

SEU 理论的核心公理：

> **理性决策可以被分解为两个独立的组成部分：对世界状态的信念（Belief）和对结果的偏好（Preference）。**

翻译成排序优化的语言：

| SEU 概念 | 排序优化对应 | 例子 |
|---------|-----------|------|
| **信念（Belief）** | 离线指标到在线指标的映射关系 | "离线 GMV +18% 大概对应在线 GMV +5%" |
| **偏好（Preference）** | 对约束违反的容忍度 | "订单量下降 2% 可以接受，下降 5% 不能忍" |
| **效用函数** | 排序目标函数 | $\text{score} = w_{\text{gmv}} \cdot f_{\text{gmv}} + w_{\text{order}} \cdot f_{\text{order}} + \ldots$ |

Savage 理论告诉我们：**信念和偏好混在一起优化是病态的**。看到 GMV -3.6%，你不知道是：
- 你的"地图"错了（信念问题：离线预测不准）
- 还是你的"价值观"错了（偏好问题：你给 GMV 的权重太高，挤压了其他指标）

这两种错误需要**相反方向**的修正，但产生的症状可能完全一样。人工靠经验猜，往往陷入恶性循环。

---

## 3. 三层架构

在进入具体机制之前，先看全局：

| 层级 | 职责 | 更新频率 | 操作者 |
|-----|------|---------|-------|
| **L1: 人类/配置** | 业务目标、约束边界、初始参数 | 低频（人工设定） | 产品经理 / 算法工程师 |
| **L2: LLM + 算法** | 信念校准 + 偏好适应 | 每轮自动（~4h） | LLM 元控制器 + LMS 回归 |
| **L3: Optuna TPE 搜索** | 在校准后的空间内搜索最优参数 | 5000 trials × 25 workers | 数值优化器 |

人类只管 L1（定方向），LLM 管 L2（调校准），数值优化器管 L3（搜参数）。各层职责清晰，不互相越界。

---

## 4. 核心机制一：Influence Share（影响力份额）

### 问题：排序结果出了问题，怎么定位原因？

传统方法是看 Kendall Tau 等排序相关性指标——两两比较 item 的排序顺序变化。但问题是：Kendall Tau 告诉你"排序变了 15%"，却不告诉你**是哪个因素导致的**。

### Influence Share 的计算

排序得分函数是加权求和：

$$
\text{score}(i) = w_{\text{gmv}} \cdot f_{\text{gmv}}(i) + w_{\text{order}} \cdot f_{\text{order}}(i) + w_{\text{ads}} \cdot f_{\text{ads}}(i) + \ldots
$$

对某个具体 item A，计算各因素的贡献：

```
f_gmv(item_A) = 50,  w_gmv = 0.6   →  contribution_gmv   = 0.6 × 50 = 30
f_order(item_A) = 30, w_order = 0.3  →  contribution_order = 0.3 × 30 = 9
f_ads(item_A) = 10,  w_ads = 0.1   →  contribution_ads   = 0.1 × 10 = 1
                                        ─────────────────────────────────
                                        total = 40

influence_share_gmv   = 30 / 40 = 75.0%
influence_share_order =  9 / 40 = 22.5%
influence_share_ads   =  1 / 40 =  2.5%
```

### 四个关键性质

1. **可分解**：每个因素的精确贡献可测量（不是黑箱）
2. **可求和**：所有份额加起来 = 100%（完整归因）
3. **单调性**：增加某因素的权重 → 该因素份额增加（符合直觉）
4. **可操作**：可以做精确的权衡推理

### 为什么比 Kendall Tau 好？

| 场景 | Kendall Tau 告诉你 | Influence Share 告诉你 |
|------|-------------------|----------------------|
| GMV 约束被违反 | "排序和上一版差了 15%" | "GMV 占影响力 75%，但 GMV 约束被违反 → 问题在 GMV 权重设得太高" |
| Orders 被挤压 | "top-10 变了 4 个 item" | "Orders 只占 22.5%，被 GMV 挤压了 → 需要从 GMV 转移影响力到 Orders" |

### 权衡操作的具体例子

```
诊断：GMV 过度优化，Orders 被挤压
决策：从 GMV 转移 10% 影响力到 Orders

调整前：                        调整后：
  w_gmv   = 0.60                  w_gmv   = 0.55  (↓)
  w_order = 0.30                  w_order = 0.35  (↑)
  w_ads   = 0.10                  w_ads   = 0.10  (=)

影响力重新分布：
  GMV:    75.0% → ~68.8%
  Orders: 22.5% → ~26.3%
  Ads:     2.5% →  ~5.0%
```

这让排序调优从"调个参数看看效果"变成了"精确分配各因素的决策影响力"。

---

## 5. 核心机制二：双通道校准（几何正交）

这是 Sortify 最精巧的设计。

### 两个通道分别管什么

**Belief 通道（信念校准）**——你的地图准不准？

| 属性 | 值 |
|------|---|
| 解决的问题 | 离线指标如何映射到在线现实？ |
| 控制变量 | `target_range`（约束边界的位置） |
| 更新方式 | LMS 回归（渐进）+ LLM 截距跳跃（大步） |
| 错误类型 | 认知性错误——你的地图和地形不匹配 |
| 几何含义 | **水平移动**约束边界 |

**Preference 通道（偏好校准）**——你有多在乎这条约束？

| 属性 | 值 |
|------|---|
| 解决的问题 | 约束违反应该被多严重地惩罚？ |
| 控制变量 | `penalty_weight`（约束边界的硬度） |
| 更新方式 | 非对称乘法缩放（违反时快升，满足时慢降） |
| 错误类型 | 公理性错误——你对"绕路"的在乎程度不对 |
| 几何含义 | **垂直缩放**违反成本 |

### 具体场景：R2 的双通道演化

```
Round 2 开始时的参数：
  target_range = [0.95, 1.05]    # Belief：离线涨 5% ≈ 在线涨 5%（天真假设）
  penalty_multiplier = 1.0       # Preference：中等惩罚
  penalty_weight = 100           # 基础惩罚权重

离线预测：GMV +18.2%
在线实际：GMV -3.6%   😱

════════════════════════════════════════════
Belief 通道启动：
════════════════════════════════════════════
  诊断：offline 严重过度乐观（差了 21.8 个百分点）
  LMS 回归：用历史 (offline, online) 数据对拟合
    → 拟合出 online ≈ 0.88 × offline - 0.08
    → new delta_intercept = -0.08
  LLM 检查：确认 LMS 方向合理，同意 -0.08
  执行：target_range 向下平移
    → new target_range = [0.92, 1.02]
    → 含义：以后离线说涨 10%，我只期望在线涨 2%~8%

════════════════════════════════════════════
Preference 通道启动：
════════════════════════════════════════════
  诊断：Orders 约束频繁被违反（6/10 batch 违反）
  判断：penalty 不够严格
  非对称更新：
    违反时的提升速率 δ_up = 0.25（快升）
    满足时的下降速率 δ_down = 0.08（慢降）
  执行：penalty_multiplier = 1.0 → 1.5
    → penalty_weight = 100 × 1.5 = 150
    → 含义：违反 Orders 约束的代价提高了 50%
```

### 为什么不能混在一起调？

想象你把 Belief 和 Preference 混在一个调节器里：

```
看到 GMV -3.6%
  → 你调了一个综合参数
  → GMV 好了一点，但 Orders 更差了
  → 你反方向调
  → Orders 好了，但 GMV 又跌了
  → 恶性循环 🔄
```

问题在于：你不知道 GMV -3.6% 是因为"你的预测不准"（信念问题）还是"你给 GMV 的权重不对"（偏好问题）。这两种情况需要的修正方向完全不同。

### 几何正交的具体含义

想象一个二维平面：

```
penalty_weight (垂直)
      ↑
      │
  200 │     ·  (Preference 调整：垂直移动)
      │     ↑
  150 │─────●───→──── (同时独立)
      │           ↓
  100 │           ·  (可以只调一个方向)
      │
      └──────┼──────┼──────→ target_range (水平)
           0.92   0.95   1.05

  Belief 调整：水平移动 target_range
  Preference 调整：垂直缩放 penalty_weight
  两个方向独立：调 Belief 不影响 Preference，反之亦然
```

这就是"几何正交"——两个通道在参数空间中的调整方向互相垂直，互不干扰。调 Belief 的工程师不用担心影响 Preference 的校准。

---

## 6. 核心机制三：LLM 元控制器

### LLM 的定位：不是调参员，是战略顾问

LLM **从不直接调底层的 7 维参数**。它只操作两个高级旋钮：

```text
delta_intercept    ∈ [-0.1, +0.1]    # 微调离线→在线映射（Belief 通道）
penalty_multiplier ∈ [0.5, 2.0]      # 缩放约束严格度（Preference 通道）
```

为什么？因为 7 维参数空间太大了，LLM 容易在里面迷路。但 LLM 擅长**模式识别和趋势推理**——"最近 3 轮 GMV 预测都偏乐观，误差在收敛"这种判断，LLM 比数值优化器强。

### 输入：结构化上下文

每轮 LLM 收到的上下文长这样：

```json
{
  "current_round": 5,
  "recent_episodes": [
    {
      "round": 4,
      "offline_prediction_gmv": "+12.5%",
      "online_actual_gmv": "+8.3%",
      "delta_intercept": -0.05,
      "belief_error": "4.2% optimistic"
    },
    {
      "round": 3,
      "offline_prediction_gmv": "+15.0%",
      "online_actual_gmv": "+9.1%",
      "delta_intercept": -0.03,
      "belief_error": "5.9% optimistic"
    }
  ],
  "recent_calibration_updates": [
    {"type": "belief", "direction": "down", "magnitude": 0.02},
    {"type": "preference", "direction": "up", "magnitude": 0.5}
  ],
  "current_parameters": {
    "delta_intercept": -0.05,
    "penalty_multiplier": 1.5
  },
  "constraint_violations": {
    "orders": {"violation_count": 3, "avg_severity": 8.2},
    "gmv": {"violation_count": 0, "avg_severity": 0}
  }
}
```

### LLM 的推理过程（伪代码）

```
ANALYZE recent_episodes:
  → R3: belief_error = 5.9% optimistic
  → R4: belief_error = 4.2% optimistic (improving!)
  → Pattern: offline GMV 预测一直过度乐观，但误差在收敛

CHECK current_parameters:
  → delta_intercept = -0.05 (已经向下调了)
  → penalty_multiplier = 1.5 (Orders 约束调得挺严)

REASON about Belief channel:
  IF belief_error 持续下降 AND 趋势向好:
    → 不需要进一步调 delta_intercept
    → 让 LMS 回归继续微调就行
    → confidence: medium (只有 2 轮数据确认趋势)

REASON about Preference channel:
  IF Orders violations 仍然高频 (3/3 rounds):
    → 需要进一步提高 penalty_multiplier
    → 证据：R3, R4, R5 都有违反
    → proposed: penalty_multiplier 1.5 → 1.8

CONFIDENCE check:
  IF 信号冲突 OR 数据不足:
    RETURN empty proposal  ← 关键安全机制

OUTPUT:
  {
    "delta_intercept_proposal": null,
    "penalty_multiplier_proposal": 1.8,
    "rationale": "Orders violations sustained at 3/3 rounds.
                  Increase penalty 1.5→1.8 to enforce stricter constraint.",
    "evidence": ["episode_R3_violations",
                 "episode_R4_violations",
                 "episode_R5_violations"]
  }
```

### 安全设计：低信心 → 空提案

这是最重要的安全机制。当 LLM 看到矛盾信号（比如 GMV 在改善但 Orders 在恶化），它会返回空提案——**不确定就不动，比瞎调强**。

### 为什么比人工调参好？

| 对比维度 | 人工 | LLM 元控制器 |
|---------|------|-------------|
| 分析速度 | 30 分钟看一轮数据 | 秒级分析 20 episodes + 30 updates |
| 历史记忆 | 依赖笔记和记忆，容易遗漏 | 结构化读取所有历史 |
| 趋势识别 | 凭经验直觉 | 量化趋势 + 证据引用 |
| 决策一致性 | 因心情/时间压力波动 | 稳定的推理框架 |
| 安全性 | 可能冒进 | 低信心 = 不动 |

---

## 7. 核心机制四：持久内存（7 表 SQLite）

### 为什么需要持久内存？

没有记忆的 Agent 每轮都在重复发现同样的规律：

```
Round 1: "哦，GMV 预测太乐观了"     → 调整
Round 2: "哦，GMV 预测太乐观了"     → 从头调整（忘了 R1 的结论）
Round 3: "哦，GMV 预测太乐观了"     → 又从头来…
```

这就是 "Groundhog Day" 问题。Sortify 用 7 张 SQLite 表解决它。

### 核心表结构

**episodes 表**：每轮的完整故事

```sql
CREATE TABLE episodes (
  round_id INT PRIMARY KEY,
  timestamp DATETIME,
  offline_metrics JSONB,       -- {"gmv": 18.2, "orders": 12.5, "ads_rev": 5.2}
  online_metrics JSONB,        -- {"gmv": -3.6, "orders": 8.3, "ads_rev": 5.1}
  parameters JSONB,            -- {"w_gmv": 0.6, "w_order": 0.3, ...}
  constraint_violations JSONB, -- {"orders": ["batch_3", "batch_7"], "ads_ctr": []}
  llm_proposal_id INT          -- 关联到 llm_proposals 表
);
```

**prior_relations 表**：世界模型的当前状态

```sql
CREATE TABLE prior_relations (
  metric_name TEXT PRIMARY KEY,
  intercept FLOAT,        -- 截距（离线→在线的基准偏移）
  slope FLOAT,            -- 斜率（离线值的缩放系数）
  last_updated INT,       -- 最后更新的轮数
  update_count INT         -- 被更新过多少次
);

-- 实例数据：
-- metric_name | intercept | slope | last_updated | update_count
-- gmv         | -0.08     | 0.88  | 4            | 3
-- orders      | +0.03     | 0.95  | 3            | 2
-- ads_rev     | -0.01     | 0.99  | 2            | 1
--
-- 解读：online_gmv ≈ 0.88 × offline_gmv - 0.08
-- 如果离线预测 GMV +18.2%，校准后的在线预期 = 0.88 × 18.2 - 8 = 8.0%
```

**prior_update_history 表**：校准日志（滚动窗口 30 条）

```sql
CREATE TABLE prior_update_history (
  update_id INT PRIMARY KEY,
  round_id INT,
  metric_name TEXT,
  update_type TEXT,        -- 'lms_regression' | 'llm_intercept_jump'
  delta_intercept FLOAT,
  reason JSONB,            -- {"offline_prediction": 18.2, "online_actual": -3.6}
  confidence FLOAT         -- 本次更新的置信度 [0, 1]
);
```

**penalty_weights 表**：约束的当前惩罚强度

```sql
CREATE TABLE penalty_weights (
  constraint_name TEXT PRIMARY KEY,
  weight FLOAT,
  last_updated INT,
  violation_history JSONB   -- 最近 10 轮的违反记录
);

-- 实例数据：
-- constraint_name | weight | violation_history
-- orders_min      | 150    | [1, 1, 0, 1, 1, 0, 1, 0, 1, 0]
-- ads_ctr_min     | 100    | [0, 0, 0, 0, 0, 1, 0, 0, 0, 0]
--
-- orders_min 经常被违反（6/10），所以 weight 从 100 升到了 150
-- ads_ctr_min 很少违反（1/10），weight 保持初始值
```

**其他 3 张表**：

```sql
penalty_weight_update_history  -- 偏好通道更新日志，窗口 30 条
llm_proposals                  -- LLM 推荐及证据引用
evidence_links                 -- 提案与 episodes 的可追溯性（审计链）
```

### 记忆如何终结 Groundhog Day

```
R1 learning:
  → 发现 GMV 预测过度乐观
  → INSERT INTO prior_relations (metric_name, intercept, slope)
    VALUES ('gmv', -0.05, 0.90)
  → INSERT INTO prior_update_history (reason)
    VALUES ('{"offline": 18.2, "online": -3.6}')

R2 learning:
  → SELECT intercept, slope FROM prior_relations WHERE metric_name = 'gmv'
  → 得到 R1 的结论：intercept = -0.05, slope = 0.90
  → 结合 R2 的新数据，LMS 回归进一步精进
  → UPDATE prior_relations SET intercept = -0.08, slope = 0.88
  → 不用从零开始！R1 的学习被继承了

R3, R4, R5...:
  → 每轮都站在前人肩膀上
  → intercept 逐渐收敛到真实值
  → 系统变得越来越准
```

---

## 8. 核心机制五：10 步 YOLO 管道

YOLO 模式下，每 ~4 小时执行一个完整周期。下面逐步拆解：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          一个 YOLO 周期（~4 小时）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[等待 3.5 小时] 积累在线 A/B 实验数据
```

**STEP 1: 拉 A/B 数据**（A/B 系统 → 本地）

```
- Pull control group metrics: GMV, Orders, Ads Revenue, CTR, ...
- Pull treatment group metrics: (用当前最新参数的实验组)
- 数据量: ~10K users × 7 days 的行为指标
- 耗时: ~2 min
```

**STEP 2: 记录到内存 DB**（原始数据持久化）

```
- 写入 episodes 表：round_id, offline_metrics, online_metrics
- 计算离线预测 vs 在线实际的差距
- 标记约束违反情况
- 耗时: ~30 sec
```

**STEP 3: LMS 回归**（自动校准离线→在线映射）

```
Input: 历史 20 轮的 (offline_pred, online_actual) 数据对
算法: 最小二乘拟合 → online = intercept + slope × offline
Output: 每个指标的新 intercept & slope

具体例子（GMV）：
  数据点: (offline_gmv, online_gmv)
    (18.2%, -3.6%), (15.0%, 9.1%), (12.5%, 8.3%), (11.8%, 7.2%), ...

  拟合结果：
    online_gmv = -0.08 + 0.88 × offline_gmv

  验证：
    offline 18.2% → 预测 online = 0.88 × 18.2 - 8.0 = 8.0%
      实际 -3.6%（还有偏差，但比不校准的 18.2% 好多了）
    offline 15.0% → 预测 online = 0.88 × 15.0 - 8.0 = 5.2%
      实际 9.1%（已经比较接近了）

- 耗时: ~1 min
```

**STEP 4: 组装 LLM 上下文**（提供推理素材）

```
- 从 episodes 表取最近 20 轮完整记录
- 从 prior_update_history 取最近 30 次校准更新
- 从 penalty_weights 取当前参数状态
- 统计约束违反频率和严重程度
- 组成结构化 JSON 上下文对象（见上文 LLM 输入示例）
- 耗时: ~10 sec
```

**STEP 5: LLM 提案**（推理框架级别调整）

```
- 送给 LLM: 上下文 JSON + few-shot prompt
- LLM 分析趋势、识别模式、量化证据
- 输出: JSON with delta_intercept & penalty_multiplier proposals
- 关键：低信心时返回空提案（安全默认）
- 耗时: ~2 min（API 延迟）
```

**STEP 6: 应用 Belief / Preference 更新**（双通道生效）

```
- 如果有 delta_intercept 提案:
    UPDATE prior_relations SET intercept = intercept + delta
    WHERE metric_name IN ('gmv', 'orders', 'ads_rev')
- 如果有 penalty_multiplier 提案:
    UPDATE penalty_weights SET weight = weight × multiplier
    WHERE constraint_name IN ('orders_min', 'ads_ctr_min')
- 记录更新到 prior_update_history / penalty_weight_update_history
- 耗时: ~20 sec
```

**STEP 7: 推导约束的目标范围**（从指标预测 → 排序约束）

```
- Input: 更新后的 prior_relations
- For each constraint:
    offline_target = [offline_gmv_min, offline_gmv_max]  # 离线期望范围
    calibrated_online = intercept + slope × offline_target  # 校准到在线
    → 这就是这轮的约束 target_range
- 例子：
    GMV: offline target [0.95, 1.05]
    校准后: [-0.08 + 0.88×0.95, -0.08 + 0.88×1.05] = [0.756, 0.844]
    → 在线 GMV 涨幅预期在 75.6%~84.4% 之间（相对基准）
- 耗时: ~30 sec
```

**STEP 8: 更新 penalty_weight**（从规范 → 约束惩罚）

```
- 检查最近 N 轮约束满足情况
- 非对称更新规则:
    违反 → 快速提高: weight × (1 + δ_up),  δ_up = 0.25
    满足 → 缓慢降低: weight × (1 - δ_down), δ_down = 0.08
- 为什么非对称？
    → 违反约束的代价远高于过度约束的代价
    → 宁可保守（高 penalty）也不要激进（低 penalty 导致约束被踩）
- 耗时: ~20 sec
```

**STEP 9: Optuna 搜索**（数值优化找最优参数）

```
- 定义 7 维参数空间（各权重的取值范围）
- 目标函数: 在满足约束的前提下，最大化 GMV（或加权多目标）
- 运行 Optuna TPE 搜索:
    5000 trials × 25 workers（完全并行）
    每个 trial: 用候选参数在离线数据上评估 → 计算目标值 + 约束违反惩罚
- Output: 最优的 7 维参数向量
- 耗时: ~25 min（这是整个管道最耗时的步骤）
```

**STEP 10: 发布到 Redis**（线上生效）

```
- 把最优参数写入 Redis KV 存储
- 排序服务实时监听 Redis key，热更新线上参数
- 下一个用户请求就用新参数排序
- 记录发布时间戳到 episodes 表
- 耗时: ~1 sec

[结束，进入 3.5h 等待期，积累新的在线数据]
```

每天约 6 轮，每轮完全自主，零人工干预。

---

## 9. 实验轨迹：Market A 的 7 轮演化（R2 → R7）

这是最有意思的部分——看系统如何从"完全不靠谱"逐步学习到"稳定可靠"。

### Round 2 (Day 0)：初始模型翻车

```
├─ offline GMV prediction: +18.2%
├─ online actual GMV: -3.6%  😱 反向了！
├─ 偏差: 21.8 个百分点，方向相反
├─ Belief diagnosis: offline 严重过度乐观
│   └─ delta_intercept: 0 → -0.08 (LLM 大幅跳跃)
│   └─ target_range: [0.95, 1.05] → [0.92, 1.02] (向下平移)
├─ Preference diagnosis: Orders 约束 6/10 batch 违反
│   └─ penalty_multiplier: 1.0 → 1.2
│   └─ penalty_weight: 100 → 120
├─ Result: GMV 没改善，但校准启动了
└─ 教训: 初始模型垃圾，但系统已经在学习
```

### Round 3 (Day 1)：曙光初现

```
├─ offline GMV: +15.0%
├─ calibrated expectation: 0.88 × 15.0 - 8.0 = 5.2%
├─ online actual: +9.1%  ✓ 好转了！
├─ Belief 误差: 从 21.8% → 5.9%（收敛中）
├─ Preference: Orders 仍违反 2/10 batch
│   └─ penalty_multiplier: 1.2 → 1.4
├─ LLM confidence: medium (只有 1 轮数据确认趋势)
└─ 信号: 校准方向正确，继续微调
```

### Round 4 (Day 2)：校准收敛

```
├─ offline GMV: +12.5%
├─ calibrated expectation: 0.88 × 12.5 - 8.0 = 3.0%
├─ online actual: +8.3%  📈
├─ Belief 误差: 4.2%，LMS 拟合精进了
├─ delta_intercept: -0.08 → -0.06（调整幅度在减小，系统趋稳）
├─ Orders constraint: 8/10 batches satisfied（好多了）
│   └─ penalty_multiplier: 1.4 → 1.3（可以略微放松）
└─ Pattern: Belief 校准在收敛，Preference 也在平衡
```

### Round 5 (Day 3)：谨慎等待

```
├─ offline GMV: +11.8%
├─ calibrated expectation: 0.88 × 11.8 - 6.0 = 4.4%
├─ online actual: +7.2%（略有回落，but within noise）
├─ LLM confidence: medium
│   └─ "是噪声还是真的恶化？unclear, need more data"
├─ delta_intercept: no change（不动，等更多信号）
├─ penalty_multiplier: no change
└─ Decision: hold steady, gather more data
    → 这就是"低信心 = 空提案"的安全机制在起作用
```

### Round 6 (Day 4)：系统成熟

```
├─ offline GMV: +14.2%
├─ calibrated expectation: 0.88 × 14.2 - 6.0 = 6.5%
├─ online actual: +8.9%  ✓
├─ Belief: converged! R4-R6 误差都 < 2%
├─ Orders: 9/10 batches satisfied
│   └─ penalty_multiplier: 1.3 → 1.2（进一步放松）
├─ delta_intercept: -0.06 → -0.05（微调，已接近最优）
└─ System maturity: 开始自我纠正，进入稳态
```

### Round 7 (Day 5)：终极验证

```
├─ offline GMV: +41.6%（激进参数实验）
├─ calibrated expectation: 0.88 × 41.6 - 5.0 = 31.6%
├─ online actual: +9.2%  🎉
│   └─ 不如预期激进，但稳定，所有约束都守住了
├─ LLM corrections: 从 R2 的 5 个 → R7 的 2 个（学习效果明显）
├─ delta_intercept: -0.05（stabilized）
├─ penalty_multiplier: 1.2（stabilized）
└─ Cumulative: 从 R2 的 GMV -3.6% → R7 的 GMV +9.2%
    → 7 轮迭代，系统自主完成了 12.8 个百分点的翻转
```

### Market B（冷启动，全新市场）

| 指标 | 7 天 A/B 结果 |
|-----|-------------|
| GMV/UU | +4.15% |
| 广告收入 | +3.58% |

冷启动市场没有历史数据，prior_relations 从默认值开始（intercept=0, slope=1），但系统在几轮内就学会了这个市场的偏差模式。

### 自主性指标

- 最长连续自主运行：**25 小时**（7 轮，无人工干预）
- LLM 每轮纠正数：从 5 个收敛到 2 个
- 每轮 LLM 成本：**$0.03–$0.10**（极低）

---

## 10. 零行人写代码：为什么这件事重要

整个 Sortify 系统——98,000 行代码、78 个模块、7 个子系统——**零行代码由人类手写**。全部由 AI coding agents 生成，单人编排。

### 传统方式构建这样的系统

```
工程师：我要设计一个排序优化框架

→ 画 ER diagram, 定义数据模型           3 天
→ 写数据模型 + 表结构                    2 天
→ 写离线评估框架                         5 天
→ 写线上部署逻辑 (Redis, A/B 集成)       5 天
→ 写监控告警                             3 天
→ Code review, bug fix, 单元测试         7 天
→ 上线, watch metrics, fix prod bugs     7 天
────────────────────────────────────────────
≈ 1.5 个月，单人，还得是 senior 级别工程师
```

### AI Agent 辅助构建

```
单人 (编排者角色):

Day 1:   定义系统设计 doc (问题定义、约束、接口、数据流)

Day 2-3: 启动多个 AI agents (并行)
         ├─ Agent A: 生成数据模型 + 7 张 SQLite 表结构
         ├─ Agent B: 生成 LMS 回归实现 + 单元测试
         ├─ Agent C: 生成 Optuna 搜索框架 + 目标函数
         ├─ Agent D: 生成 API 集成层 + Redis 发布
         └─ Agent E: 生成 LLM 元控制器 + prompt 模板

Day 4:   审查所有代码，修复集成 bug，指导改进

Day 5:   Agent F 生成端到端测试、部署脚本、监控

Day 6-7: 集成测试、手工 smoke test、灰度上线
────────────────────────────────────────────
≈ 1 周，单人
```

### 关键区别

| 维度 | 传统方式 | AI Agent 辅助 |
|------|---------|-------------|
| 工程师角色 | 手写每一行代码 | 审查、指导、编排 |
| Context window | 一个功能模块 | 整个系统架构 |
| 开发模式 | 串行（先 A 再 B 再 C） | 并行（ABCDE 同时跑） |
| 人的瓶颈 | 编码速度 | 架构设计 + 审查质量 |
| 时间 | ~1.5 个月 | ~1 周 |

**这不是"AI 替代人"，而是"人的杠杆率提升了 3-5 倍"。** 编排者需要对整个系统有深刻理解——你得知道要什么、怎么拆分、如何验证。AI agents 加速的是执行，不是思考。

系统基于 [ParaDance](https://pypi.org/project/paradance/)（101K+ PyPI 下载）构建。

---

## 11. 启示：带走什么？

### 1. 决策理论不是摆设

Savage SEU 理论在这里不是装饰性引用，而是直接指导了架构设计。Belief/Preference 分离解决了真实存在的诊断纠缠问题。下次设计系统时，想想：**我的系统里有没有把"对世界的认知"和"对结果的偏好"混在一起？**

### 2. LLM 不该直接调参数

让 LLM 操作高层语义旋钮（校准截距、惩罚系数），而不是底层数值参数。LLM 擅长模式识别和趋势推理，不擅长精确数值优化。把数值优化留给 Optuna 这样的专业工具。

### 3. 记忆是自主性的基础

没有跨轮次记忆，Agent 每轮都在重复发现同样的规律。7 表 SQLite 看起来简单，但它是 YOLO 模式能持续 25 小时自主运行的关键。任何需要迭代改进的 Agent 系统，都需要某种形式的持久记忆。

### 4. 安全靠设计，不靠祈祷

低信心返回空提案、双通道正交、有界的调节范围（delta_intercept ∈ [-0.1, +0.1]）——这些约束让 Agent 在"不确定"时默认安全。设计 Agent 系统时，**先想"怎么防止它搞砸"，再想"怎么让它更强"**。

### 5. 非对称更新是实践智慧

违反约束时快速提高惩罚（δ_up = 0.25），满足约束时缓慢降低（δ_down = 0.08）。这种"快升慢降"的非对称设计，反映了一个务实的工程判断：**过度约束的代价远小于约束失控的代价**。

---

**参考资源**

- [Sortify 项目主页](https://github.com/yinsn/sortify-resources)
- [技术报告（中文 PDF）](https://github.com/yinsn/sortify-resources/blob/main/docs/Sortify-Technical-Report-zh.pdf)
- [设计文档（中文）](https://github.com/yinsn/sortify-resources/blob/main/docs/design/zh)
- [知乎博客文章](https://github.com/yinsn/sortify-resources/blob/main/blog/zhihu_post.md)
- [Demo 视频](https://github.com/yinsn/sortify-resources/blob/main/docs/sortify-demo.mp4)
- [ParaDance (PyPI)](https://pypi.org/project/paradance/)
- [Savage 主观期望效用理论 (Wikipedia)](https://en.wikipedia.org/wiki/Subjective_expected_utility)
