---
title: "记一次模型训练 NaN 的排查过程：从 18MB 日志里揪出真凶"
date: 2026-03-01
tags:
  - 机器学习
  - 模型调试
  - MoE
  - 训练稳定性
lang: zh
english: machine-learning/debugging/nan-debug-moe-training.en
---

> 🌐 [Read in English](./nan-debug-moe-training.en.md)

> 模型训着训着突然 loss 变成了 NaN，到底是梯度爆炸还是前向溢出？面对 18MB 的 debug 日志，我是怎么一步步定位到根因的。

## 问题现象

某天训练一个带 MoE（Mixture of Experts）的推荐模型，跑了一段时间后，两个 worker 同时报出 NaN。拿到的日志是框架的 `DebugTensorMaxNorm` traceback，每个 worker 一份，各 18MB，近 3 万行。

打开日志一看，满屏的 `[nan]`，密密麻麻的。直觉反应是"梯度爆了"，但真是这样吗？

## 先搞懂日志在说什么

在动手之前，先理解日志格式：

```
[DebugTensorMaxNorm][Backtrace_N <trace_target>] [<op_name>:<output_index>] [<max_norm_value>]
```

三个关键字段：

- **`Backtrace_N`**：回溯深度。`N=0` 是最终输出（比如 `total_loss`），N 越大越接近计算图的底层。可以理解为：`Backtrace_0` 是"果"，`Backtrace_N` 是"因"。
- **`trace_target`**：追踪目标。`total_loss` 是前向传播链路，`raw_dense_grad` 是梯度链路，`sparse_norm_square` 是稀疏参数的梯度范数。
- **`max_norm_value`**：tensor 的最大范数。正常是有限数，异常是 `nan` 或 `inf`。

搞清楚这个结构后，排查思路就清晰了：**沿着 Backtrace 从浅到深追溯，找到第一个"变坏"的算子**。

---

## Step 1：先分区——NaN 出现在前向还是反向？

面对 3 万行日志，第一件事不是逐行看，而是**分区搜索**。

NaN 无非两种来源：

- **前向传播**：某个算子的输出溢出了（激活值太大）
- **反向传播**：梯度爆炸了

搜一下就知道：

```bash
# 搜前向传播中的异常值
grep -n "total_loss.*\[nan\]\|total_loss.*\[inf\]" traceback.log | head -20

# 搜反向传播中的异常值
grep -n "raw_dense_grad.*\[nan\]\|raw_dense_grad.*\[inf\]" traceback.log | head -20
```

结果：

```
# 前向传播
[Backtrace_0 total_loss] [add_223:0] [nan]
...
[Backtrace_16 total_loss] [logistic_loss_77:0] [nan]
[Backtrace_16 total_loss] [InterFusion_output_1/Mean:0] [inf]  ← 注意！是 inf 不是 nan
```

**关键发现**：前向传播里不只有 `nan`，还有 `inf`。

这一下就改变了排查方向——**如果是纯梯度爆炸，前向传播应该全是正常值**。现在前向已经有 `inf`，说明问题出在前向传播，梯度的 `nan` 只是前向 `nan` 的连锁反应。

> **经验法则**：看到 `inf` 比看到 `nan` 更有信息量。`nan` 可能是各种运算产生的（0/0、inf-inf 等），但 `inf` 通常意味着数值溢出，指向性更明确。

---

## Step 2：追溯 `inf` 链路——找到第一个溢出的算子

既然前向有 `inf`，那就沿着 `inf` 往深层追。**找 Backtrace_N 最大的那个 `inf`，它就是第一个溢出的地方。**

```bash
grep -n "\[inf\]" traceback.log
```

结果非常清晰：

```
Backtrace_15 → [concat_47:0] [inf]
Backtrace_16 → [InterFusion_output_1/Mean:0] [inf]
Backtrace_17 → [InterFusion_layer_3/add_1:0] [inf]
Backtrace_18 → [InterFusion_layer_3/.../mlp_1/add:0] [inf]
Backtrace_19 → [InterFusion_layer_3/.../sparse_mo_e_4/Reshape_6:0] [inf]
Backtrace_20 → [InterFusion_layer_3/.../sparse_mo_e_4/MoeGatherForward:0] [inf]
Backtrace_21 → [InterFusion_layer_3/.../down_1/MoeGroupedGemmForward:0] [inf]  ← 最深！
```

**锁定**：`Backtrace_21` 的 `MoeGroupedGemmForward`（MoE Expert 的 down projection 矩阵乘法）是第一个产生 `inf` 的算子。

---

## Step 3：检查该算子的输入——为什么矩阵乘法会溢出？

`MoeGroupedGemmForward` 就是矩阵乘法（GEMM）。矩阵乘法溢出，要么是权重太大，要么是输入激活值太大。

```bash
grep "InterFusion_layer_3.*mlp" traceback.log | grep "Backtrace_2[1-3]"
```

```
# 产生 inf 的算子及其上下文（Backtrace_21）
InterFusion_layer_3/.../mlp_share/mul          → 24,976   ← 激活值已经巨大！
InterFusion_layer_3/.../MLP_down_1/kernel      → 1.98     ← 权重很正常
InterFusion_layer_3/.../MLP_down_1/MatMul      → 12,676   ← shared MLP 的乘法结果
InterFusion_layer_3/.../ln2_1/moments/variance → 53,593
```

真相浮出水面：

- **权重本身不大**（kernel MaxNorm 才 ~2.0），不是权重爆炸
- **输入激活值已经到了 24,976**，这才是根因
- LayerNorm 的方差都到了 53,593，说明这一层的数值分布已经完全失控

---

## Step 4：横向对比各层——是单层问题还是系统性膨胀？

| InterFusion 层 | Shared MLP 输出 MaxNorm | MoE Expert 输出 MaxNorm |
|:--------------:|:-----------------------:|:-----------------------:|
| layer_0        | 979                     | 23                      |
| layer_1        | 1,402                   | 60                      |
| layer_2        | 993                     | 54                      |
| **layer_3**    | **12,676**              | **inf**                 |

layer_0 到 layer_2 的 shared MLP 输出在 ~1000 量级，但 **layer_3 突然跳到了 12,676——比其他层大了 10 倍以上**。这不像是逐层均匀放大，更像是 layer_3 存在某种放大效应，使得激活值在这里急剧膨胀。

---

## Step 5：验证 inf → nan 的因果链

```
Backtrace_22:
[Mul_476:0]           → [-inf]   ← inf 经过负号变成 -inf
[logistic_loss_71:0]  → [nan]    ← log(1 + exp(-inf)) 产出 nan
[logistic_loss_73/Exp:0] → [nan] ← exp(nan) = nan，开始扩散
```

**传播链路完全对得上**：

```
MoE down projection 输出 inf
  → InterFusion_layer_3 输出 inf
  → 模型最终输出 inf
  → logistic_loss(inf) = nan
  → 反向传播全部 nan
```

---

## Step 6：最后确认——梯度没有独立问题

梯度的 nan 恰好在 `Backtrace_22` 才出现，与前向传播的时间线完全一致。**梯度侧没有独立的 nan 来源**，纯粹是前向 nan 反传回来的结果。

---

## 最终结论

```
根因: InterFusion_layer_3 的 MoE Expert (sparse_mo_e_4) 的 down projection
      (MoeGroupedGemmForward) 输出溢出为 inf

原因: 该层 shared MLP 的激活值已膨胀至 24,976（其他层 ~1,000），
      经过 MoE expert 矩阵乘法后超出浮点数表示范围 → inf

本质: 不是突发的梯度爆炸，而是前向激活值在训练过程中逐步膨胀，
      InterFusion_layer_3 最严重，最终在某个 step 突破浮点上限
```

---

## 排查方法论：分区、追深、比宽

```
分区：区分前向 vs 反向，确定 NaN 起源于哪个阶段
  ↓
追深：沿 Backtrace 从浅到深追溯，找到第一个产生 inf/nan 的算子
  ↓
查因：检查该算子的输入，判断是权重问题还是激活值问题
  ↓
比宽：横向对比各层同类算子的数值，判断是单点异常还是系统性膨胀
  ↓
验证：确认 nan 传播链路的因果关系，排除其他独立 nan 来源
```

**实用 tips**：

1. **先搜 `inf` 再搜 `nan`**。`inf` 的信息量远大于 `nan`，它明确告诉你"数值溢出了"
2. **看 Backtrace 编号**。编号最大的异常值 = 计算图中最底层的异常 = 最接近根因
3. **权重和激活值分开看**。权重正常但激活值爆了，说明是前面层的累积效应
4. **横向对比同类算子**。对比同架构不同层的值才能看出哪里是异常点
5. **前向有 inf/nan 时，不要急着看梯度**。先把前向链路追清楚

---

## 可能的修复方向

- 对 MoE expert 的输出加 activation clipping
- 检查 InterFusion_layer_3 的 LayerNorm epsilon（当前 `1e-6`，在 variance=53593 的情况下形同虚设）
- 加入 gradient clipping 防止权重持续增长
- 监控各层激活值 MaxNorm，在膨胀早期就介入（比如动态调低学习率）
- 考虑在 InterFusion 层之间加 post-norm 或 activation scaling
