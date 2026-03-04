---
title: "工业级推荐模型 Serving Profile 分析指南"
date: 2026-03-03
tags:
  - 推荐系统
  - Serving
  - 性能优化
  - Profile
  - Roofline Model
lang: zh
english: recommender-systems/serving/serving-profile-guide.en
---

> 🌐 [Read in English](./serving-profile-guide.en.md)


---

## 第一部分：Profile 是什么，为什么要做

Serving Profile 的核心问题就一个：**一次推理请求的时间花在哪了？**

推荐系统的 serving 延迟直接影响用户体验。一个精排模型如果 P99 从 20ms 涨到 50ms，可能导致整个请求链路超时。Profile 就是找到"时间都去哪了"，然后有的放矢地优化。

---

## 第二部分：四个分析维度

```
                    ┌─────────────────────┐
                    │   端到端延迟 (E2E)    │
                    └──────────┬──────────┘
           ┌──────────────┬────┴────┬───────────────┐
           ▼              ▼         ▼               ▼
    ┌────────────┐ ┌──────────┐ ┌────────┐ ┌─────────────┐
    │  特征获取   │ │ 图计算   │ │ 内存IO │ │  系统开销    │
    │ (Feature)  │ │ (Compute)│ │(Memory)│ │  (System)   │
    └────────────┘ └──────────┘ └────────┘ └─────────────┘
```

### 维度一：特征获取 (Feature Retrieval)

这一步是从存储系统中拉取模型所需的输入特征，包括稀疏 embedding 查表（从参数服务器拉取）、稠密特征获取（从 Feature Store 拉取用户/物品画像）、序列特征拼装（用户历史行为序列的 padding/truncation）。

在工业推荐系统中，这一步通常占总延迟的 **40-60%**。很多人只关注模型计算，忽略了特征获取，这是一个常见误区。

**怎么衡量：** 端到端延迟 - 纯图计算延迟 = 特征获取 + 系统开销。也可以在推理框架中单独打点。

### 维度二：图计算 (Graph Compute)

模型前向推理的实际算子计算时间。瓶颈通常在 MatMul（全连接层、Attention 的 QKV 投影）、Attention Score 计算（O(n²) 的序列长度）、MoE Routing + Expert 计算。

**怎么衡量：** TF Timeline / PyTorch Profiler / nsys 都可以拿到 op 级别的耗时。

### 维度三：内存 IO (Memory Bandwidth)

推荐模型和 CV/NLP 模型有一个根本区别：**推荐模型通常是 memory-bound 而不是 compute-bound**。原因是推荐模型的 batch size 通常很小（几十到几百），矩阵乘法的计算强度不够，GPU 的算力用不满，瓶颈反而在内存读写带宽上。

具体表现为：模型参数的 load/store（尤其是 embedding table）、中间 tensor 的分配和回收、GPU/CPU 间数据搬运（Host-Device Copy）。

**怎么衡量：** nsys 的 Memory Throughput 指标，或者通过 Roofline Model 分析（后面会讲）。

### 维度四：系统开销 (System Overhead)

框架层面的非计算开销，包括 RPC 调用延迟（推理框架的请求/响应序列化）、Batching 的等待时间（凑 batch 的延迟）、图调度开销（TF runtime 的 op scheduling）、小算子的 kernel launch 开销。

**怎么衡量：** 在 Timeline 中看算子之间的空白间隔。如果 GPU Timeline 上有大量空白，说明系统开销大。

---

## 第三部分：静态分析（不需要跑模型）

静态分析是 Profile 的第一步。只需要模型代码或计算图定义，不需要真正运行模型。目的是在跑 Profile 之前，先有一个预期——哪些模块"应该"是瓶颈。

### 3.1 参数量分析

逐层统计权重矩阵的形状，相乘求和。

```
全连接层 Dense(in, out):    参数量 = in × out + out (bias)
Attention(d_model, n_heads): 参数量 = 4 × d_model² (Q,K,V,O 各一个投影)
MoE(n_experts, expert_size): 参数量 = n_experts × expert_size
LayerNorm(dim):              参数量 = 2 × dim (scale + bias)
Embedding(vocab, dim):       参数量 = vocab × dim
```

**实际操作：** 在代码中搜索所有创建权重的 API（`tf.Variable`、`nn.Linear`、`nn.Embedding` 等），记录 shape，汇总。

### 3.2 FLOPs 分析

```
全连接层:    FLOPs = 2 × batch × in_dim × out_dim
Attention:   FLOPs ≈ 4 × batch × seq_len² × d_model  (QK^T + score×V)
                    + 8 × batch × seq_len × d_model²  (QKV + O 投影)
MoE:         FLOPs = (topk / n_experts) × 所有 expert 的总 FLOPs
Conv1D:      FLOPs = 2 × batch × out_channels × kernel_size × in_channels × seq_len
```

**一个直觉：** 对于典型的多任务精排模型，假设有一个 4 层 Transformer 主干（dim=512, 32 tokens）和 40 个预估头（[64,32,1]）：
- 主干 FLOPs ≈ 4 × (8×32²×512 + 8×32×512²) ≈ ~140M
- 40 个预估头 ≈ 40 × (2×512×64 + 2×64×32 + 2×32) ≈ ~3M
- 主干占了 98% 的计算量，但预估头可能因为 kernel launch 开销反而耗时不少

### 3.3 Tensor Shape 传播分析

这是最实用的静态分析技巧：**追踪主要 tensor 在图中的 shape 变化，找到维度突然增大的地方。**

```
典型推荐模型的数据流：

Embedding Lookup  → (B, ~2000-5000)     ← 所有特征拼接，维度很宽
  → Token 化       → (B, N_tokens, D)    ← 投影到统一维度
  → 主干网络       → (B, N_tokens, D)    ← 维度不变
  → Pooling/Reduce → (B, D)             ← 压缩 token 维度
  → 预估头         → (B, 1) × N_tasks   ← 每个任务一个输出
```

维度骤变的地方就是潜在瓶颈。比如"所有特征拼接"那一步的维度可能有几千，投影到 N_tokens × D 的过程需要大量 MatMul。

### 3.4 图结构分析

如果你有导出的计算图（TF 的 GraphDef、ONNX 等），可以统计：

```python
# TensorFlow 示例
import tensorflow as tf

graph_def = tf.GraphDef()
with open('saved_model.pb', 'rb') as f:
    graph_def.ParseFromString(f.read())

# 统计 op 类型分布
op_counts = {}
for node in graph_def.node:
    op_counts[node.op] = op_counts.get(node.op, 0) + 1

for op, count in sorted(op_counts.items(), key=lambda x: -x[1])[:15]:
    print(f"{op}: {count}")

# 典型结果：
# Const: 3000+    ← 模型参数
# MatMul: 200+    ← 主要计算
# Add: 150+       ← 残差连接、bias
# Reshape: 100+   ← shape 变换
```

如果 MatMul 数量远超预期（比如 200+ 个），说明有很多小矩阵乘法，可能可以合并。

---

## 第四部分：动态 Profile（需要跑模型）

### 4.1 TensorFlow Timeline

最基础的方法，适用于 TF 1.x 和 2.x：

```python
import tensorflow as tf
from tensorflow.python.client import timeline

run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
run_metadata = tf.RunMetadata()

result = sess.run(
    fetches=output_tensors,
    feed_dict=feed_dict,
    options=run_options,
    run_metadata=run_metadata
)

# 导出 Chrome Trace 格式
tl = timeline.Timeline(run_metadata.step_stats)
with open('timeline.json', 'w') as f:
    f.write(tl.generate_chrome_trace_format())

# 打开 chrome://tracing/ 加载 timeline.json
```

### 4.2 PyTorch Profiler

如果是 PyTorch 模型：

```python
import torch
from torch.profiler import profile, record_function, ProfilerActivity

with profile(
    activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
    record_shapes=True,
    profile_memory=True,
    with_stack=True
) as prof:
    with record_function("model_inference"):
        output = model(input_data)

# 打印表格
print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=20))

# 导出 Chrome Trace
prof.export_chrome_trace("trace.json")

# 导出 TensorBoard 格式
prof.export_stacks("stacks.txt", "self_cuda_time_total")
```

### 4.3 NVIDIA nsys / Nsight Systems

GPU 级别的底层 Profile：

```bash
# 采集
nsys profile \
    --trace=cuda,cudnn,cublas,nvtx \
    --cuda-memory-usage=true \
    --output=serving_profile \
    python run_inference.py

# 生成 .nsys-rep 文件
# 用 Nsight Systems GUI 打开（可以看到 GPU kernel 级别的时间线）
```

### 4.4 怎么读 Timeline

```
典型的推理 Timeline 布局：

时间 →  0ms          5ms          10ms         15ms         20ms
CPU  │███ Preprocess ███│░│██ Schedule ██│░░░░░│█ Postprocess █│
     │                  │ │             │     │               │
GPU  │                  │░│████ Attn ████████│░│██ MLP ██│░░░│
     │                  │ │                  │ │         │   │
     ├──────────────────┤ ├──────────────────┤ ├─────────┤   │
     │   特征准备 5ms    │ │  主干计算 8ms     │ │ 输出 3ms │   │
```

**看什么：**

1. **长色块** = 耗时大的算子，优先优化对象
2. **空白间隔** = 等待/调度开销。如果 GPU 上有大量空白，说明 kernel launch 或 CPU-GPU 同步是瓶颈
3. **CPU 和 GPU 的重叠度**：理想情况下 CPU 在准备下一个 batch 的特征时，GPU 在计算当前 batch。如果两者串行，说明 pipeline 没做好
4. **Memory Copy 事件**：如果 HtoD / DtoH 的 copy 占比大，考虑 pinned memory 或减少搬运

### 4.5 多次 Profile 取中位数

Profile 数据有波动，一次结果不可靠。最佳实践：

```python
# Warmup：前几次推理不计入统计（JIT 编译、缓存预热等）
for _ in range(10):
    sess.run(output_tensors, feed_dict=feed_dict)

# 正式采集：跑 50-100 次取中位数
import time
latencies = []
for _ in range(100):
    start = time.perf_counter()
    sess.run(output_tensors, feed_dict=feed_dict)
    latencies.append((time.perf_counter() - start) * 1000)

import numpy as np
print(f"P50: {np.percentile(latencies, 50):.2f}ms")
print(f"P90: {np.percentile(latencies, 90):.2f}ms")
print(f"P99: {np.percentile(latencies, 99):.2f}ms")
```

---

## 第五部分：分析 Profile 结果的方法论

### 5.1 瓶颈分类法

拿到 profile 数据后，把耗时最长的算子分成三类：

```
┌─────────────────────────────────────────────────────────────────┐
│                  Compute-Bound (计算瓶颈)                        │
│  特征：GPU 利用率高，FLOPs 大，算力打满                            │
│  典型：大矩阵乘法、长序列 Attention (O(n²))                       │
│  优化：减少计算量（降维、减层、剪枝、量化、用更高效的算子）            │
│  例子：4层 512维 Transformer 的 Attention                        │
├─────────────────────────────────────────────────────────────────┤
│                  Memory-Bound (内存瓶颈)                         │
│  特征：GPU 利用率低，内存带宽打满                                  │
│  典型：Embedding Lookup、大 tensor concat、gather/scatter         │
│  优化：减少内存访问（算子融合、减少中间 tensor、量化参数）             │
│  例子：几百个 embedding slot 的查表和拼接                          │
├─────────────────────────────────────────────────────────────────┤
│                  Latency-Bound (延迟瓶颈)                        │
│  特征：GPU 利用率低，带宽也没打满，大量空闲间隔                      │
│  典型：过多小算子(kernel launch)、串行依赖链、RPC 等待               │
│  优化：算子融合、增加并行度、异步执行、减少 op 数量                   │
│  例子：50 个独立的小 MLP 预估头串行执行                             │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Roofline Model

Roofline Model 是定量判断瓶颈类型的理论工具。核心概念是"算术强度"：

```
算术强度 = 算子的 FLOPs ÷ 算子需要读写的内存字节数 (FLOPs/Byte)
```

```
性能                     ┌─── Compute Bound 区域 ───
(FLOPs/s)  ──────────────┤  峰值算力 (如 A100: 312 TFLOPs bf16)
                        /│
                       / │
                      /  │
                     /   │
    Memory Bound    /    │
        区域       /     │
                  /      │
─────────────────/───────┴──────────────────────
                拐点     算术强度 (FLOPs/Byte)
```

**拐点 = 峰值算力 ÷ 内存带宽**

以 A100 为例：312 TFLOPs (bf16) ÷ 2 TB/s (HBM) ≈ 156 FLOPs/Byte。

算术强度 < 156 → Memory Bound，优化方向是减少内存访问。
算术强度 > 156 → Compute Bound，优化方向是减少计算量。

**典型推荐模型算子的算术强度：**

```
算子                     算术强度        瓶颈类型
────────────────────────────────────────────────
Embedding Lookup         ~1             极度 Memory Bound
小 MatMul (B=32, M=1)   ~10-30         Memory Bound
大 MatMul (B=1024)       ~200+          Compute Bound
Attention (seq=32)       ~20-50         Memory Bound
Attention (seq=1024)     ~200+          Compute Bound
LayerNorm                ~5-10          Memory Bound
Activation (ReLU/GELU)  ~1             Memory Bound
```

**关键洞察：** 推荐模型 serving 时 batch size 通常很小（不像训练那样上千），所以大部分算子都落在 Memory Bound 区域。这意味着"减少 FLOPs"未必能降低延迟，减少内存访问（比如算子融合、避免不必要的 copy）可能更有效。

### 5.3 Amdahl 定律

优化一个模块的收益上限取决于它在总延迟中的占比：

```
加速比 = 1 / ((1 - P) + P/S)

P = 被优化模块占总延迟的比例
S = 该模块的加速倍数
```

例如：主干网络占总延迟 30%，你把它加速了 2 倍：

```
加速比 = 1 / ((1-0.3) + 0.3/2) = 1 / 0.85 = 1.18x
```

只快了 18%。如果特征获取占 50%，你完全消除了它（S=∞）：

```
加速比 = 1 / (1-0.5) = 2x
```

**教训：** 先搞清楚各部分的时间占比，再决定优化哪里。不要一上来就去优化 Attention 实现——如果特征获取占了 60%，模型计算优化到极致也只能快 40%。

---

## 第六部分：推荐模型特有的 Profile 关注点

推荐模型的 serving 和 NLP/CV 模型有几个重要区别，Profile 时要特别关注：

### 6.1 候选共享 (Candidate Sharing)

推荐系统的精排通常一次请求包含 N 个候选物品。模型中有些计算只依赖用户侧，可以在 N 个候选间共享（算一次），有些依赖物品侧或交叉，每个候选都要算。

```
                    ┌──────────────────────┐
                    │    User-Side 计算     │  ← 算 1 次
                    │  (用户序列编码等)       │
                    └──────────┬───────────┘
                               │ broadcast
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
        ┌──────────┐    ┌──────────┐      ┌──────────┐
        │ 候选 1    │    │ 候选 2    │      │ 候选 N    │  ← 算 N 次
        │ 交叉计算  │    │ 交叉计算  │ ...  │ 交叉计算  │
        └──────────┘    └──────────┘      └──────────┘
```

**Profile 时要区分：** 哪些算子被调用了 1 次 vs N 次。如果某个本应共享的计算被错误地调用了 N 次，那就是严重的浪费。

### 6.2 Embedding 查表开销

推荐模型通常有几百个特征 slot，每个 slot 对应一个 embedding table。这些 embedding 通常存储在参数服务器（PS）上，serving 时需要通过 RPC 查表。

```
Embedding 查表延迟 = 网络 RTT + PS 查询时间 + 序列化/反序列化

影响因素：
- slot 数量（越多，查询次数或 batch 越大）
- embedding 维度（越大，传输数据越多）
- PS 的负载和缓存命中率
- 是否做了 prefetch / 异步查询
```

这个延迟在 Timeline 中通常表现为 GPU 空闲等待 CPU 喂数据。

### 6.3 多任务预估头

工业级精排模型通常有几十个预估目标（CTR、CVR、停留时长、关注、评论、分享等），每个目标一个小 MLP 头。

单个头很小（如 [256, 64, 32, 1]，参数量几万），但：
- 数量多（30-50 个），总计时间可观
- 每个头是独立的小 kernel，GPU 利用率低
- kernel launch 开销可能超过计算本身

**优化思路：** 把多个相同结构的 MLP 头合并成一次大矩阵乘法（batched MatMul），减少 kernel 数量。

### 6.4 Write-back / 在线更新

有些模型在 serving 时会更新 embedding（比如实时学习、write-back 机制）。这个更新操作（assign graph）可能非常大，需要关注它的执行频率和耗时，以及是否和推理图共享 GPU 资源导致互相干扰。

---

## 第七部分：Profile 的完整流程 Checklist

### Step 1: 准备

```
□ 明确优化目标：P99 延迟目标是多少？当前是多少？
□ 确认 serving 环境：什么硬件？什么推理框架？
□ 准备代表性输入：batch size、序列长度、候选数量要和线上一致
□ 确认模型版本：和线上 serving 的版本完全一致
```

### Step 2: 静态分析

```
□ 参数量分析：总参数量多少？各模块占比？
□ FLOPs 分析：总 FLOPs 多少？各模块占比？
□ Tensor shape 传播：哪里有维度突变？
□ Op 统计：有多少个 op？MatMul 数量？小算子数量？
□ 建立初步假设：预期哪个模块是瓶颈？
```

### Step 3: 动态 Profile

```
□ Warmup：跑 10+ 次预热
□ 多次采样：跑 100 次取 P50/P90/P99
□ 采集 Timeline：TF Timeline / PyTorch Profiler / nsys
□ 如果有 GPU：同时采集 GPU kernel trace
□ 如果涉及 PS：同时采集 RPC 延迟分布
```

### Step 4: 分析

```
□ 端到端延迟拆解：特征获取 vs 图计算 vs 系统开销各占多少？
□ Top-10 耗时算子：哪些算子最慢？
□ 瓶颈分类：Compute-Bound / Memory-Bound / Latency-Bound？
□ Roofline 分析：关键算子的算术强度是多少？
□ 候选共享检查：应该共享的计算确实只算了一次吗？
□ 小算子问题：有多少 < 0.01ms 的算子？launch 开销总和多少？
□ 内存分析：峰值显存多少？有没有不必要的中间 tensor？
□ 对比静态预期：和 Step 2 的假设一致吗？如果不一致说明了什么？
```

### Step 5: 优化与验证

```
□ 按 Amdahl 定律排优先级：先优化占比最大的瓶颈
□ 优化后重新 Profile：确认效果符合预期
□ 回归测试：确认精度没有下降
□ 线上 A/B：确认端到端效果
```

---

## 第八部分：常见优化手段速查

```
瓶颈类型          优化手段                          预期收益
────────────────────────────────────────────────────────────
Compute-Bound
                  减少 Attention 层数               线性降低
                  降低维度 (dim 512→256)            平方级降低
                  序列截断 (1024→512)               平方级降低 (Attention)
                  量化 (FP32→FP16/INT8)            2-4x
                  用更高效的 Attention 变体          视情况

Memory-Bound
                  算子融合 (op fusion)              减少 load/store
                  减少 embedding 维度               线性降低
                  使用 FP16/BF16 参数               2x 带宽节省
                  Embedding 缓存 / Prefetch         减少 PS 查表次数
                  减少不必要的 tensor copy           case by case

Latency-Bound
                  合并小算子 (batched MLP heads)     减少 kernel launch
                  TF/PyTorch 图优化 (XLA/TorchScript) 自动 fusion
                  异步执行 (CPU-GPU pipeline)         隐藏等待
                  减少预估头数量                      线性降低
                  候选共享 (user-side 只算一次)        N 倍降低(对共享部分)
```

---

## 附录：Chrome Trace JSON 格式说明

当你在 `chrome://tracing/` 中打开 timeline.json 时，文件格式如下：

```json
{
  "traceEvents": [
    {
      "name": "MatMul",          // 算子名称
      "cat": "Op",               // 类别
      "ph": "X",                 // X=完整事件(有持续时间)
      "ts": 1000,                // 开始时间 (微秒)
      "dur": 500,                // 持续时间 (微秒)
      "pid": "GPU:0",            // 设备
      "tid": "stream:0",         // 线程/流
      "args": {                  // 附加信息
        "op": "MatMul",
        "input_shapes": "[[32,512],[512,256]]"
      }
    }
  ]
}
```

**交互操作：**
- W/S 键：放大/缩小时间轴
- A/D 键：左右平移
- 点击色块：查看算子详情（name、duration、input shapes）
- 按 `/` 搜索算子名称
- M 键：标记选中区域的时间范围
