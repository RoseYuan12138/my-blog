---
title: "Serving Profile Analysis Guide for Industrial Recommendation Models"
date: 2026-03-03
tags:
  - recommender systems
  - serving
  - performance optimization
  - profiling
  - roofline model
lang: en
chinese: recommender-systems/serving/serving-profile-guide
---

> 🌐 [中文版](./serving-profile-guide.md)

---

## Part 1: What Is Profiling and Why Do It

Serving profiling answers one question: **where does the time go during a single inference request?**

Serving latency in recommendation systems directly affects user experience. If a ranking model's P99 jumps from 20ms to 50ms, the entire request chain may time out. Profiling finds where the time is going so you can optimize with precision.

---

## Part 2: Four Analysis Dimensions

```
                    ┌─────────────────────┐
                    │   End-to-End (E2E)   │
                    └──────────┬──────────┘
           ┌──────────────┬────┴────┬───────────────┐
           ▼              ▼         ▼               ▼
    ┌────────────┐ ┌──────────┐ ┌────────┐ ┌─────────────┐
    │  Feature   │ │  Graph   │ │ Memory │ │   System    │
    │ Retrieval  │ │ Compute  │ │   IO   │ │  Overhead   │
    └────────────┘ └──────────┘ └────────┘ └─────────────┘
```

### Dimension 1: Feature Retrieval

This step pulls the model's input features from storage: sparse embedding lookups (from parameter servers), dense feature retrieval (user/item profiles from a Feature Store), and sequence feature assembly (padding/truncation of user history).

In industrial recommendation systems, this step typically accounts for **40–60% of total latency**. A common mistake is focusing only on model computation while ignoring feature retrieval.

**How to measure:** E2E latency − pure graph compute latency = feature retrieval + system overhead. You can also add explicit timing points in the inference framework.

### Dimension 2: Graph Compute

The actual operator computation time during forward inference. Bottlenecks typically appear in MatMul (dense layers, QKV projections in Attention), Attention score computation (O(n²) in sequence length), and MoE routing + expert computation.

**How to measure:** TF Timeline, PyTorch Profiler, or nsys all provide op-level timing.

### Dimension 3: Memory Bandwidth

A key difference between recommendation models and CV/NLP models: **recommendation models are typically memory-bound, not compute-bound**. Because batch sizes at serving time are small (tens to hundreds), matrix multiplications don't achieve high arithmetic intensity — GPU compute is underutilized and the bottleneck is memory bandwidth instead.

This manifests as: parameter load/store (especially embedding tables), intermediate tensor allocation and deallocation, and Host-Device data transfers.

**How to measure:** Memory Throughput metrics in nsys, or Roofline Model analysis (covered below).

### Dimension 4: System Overhead

Non-computational overhead at the framework level: RPC call latency (request/response serialization), batching wait time (waiting to fill a batch), graph scheduling overhead (TF runtime op scheduling), and kernel launch overhead for small ops.

**How to measure:** Look for blank gaps between operators in the Timeline. Large blank regions on the GPU timeline indicate high system overhead.

---

## Part 3: Static Analysis (No Model Execution Required)

Static analysis is the first step. It only requires model code or a compute graph definition — no actual run needed. The goal is to form expectations *before* profiling: which modules *should* be the bottleneck?

### 3.1 Parameter Count Analysis

Count weight matrix shapes layer by layer and sum the products.

```
Dense(in, out):              params = in × out + out (bias)
Attention(d_model, n_heads): params = 4 × d_model²  (Q, K, V, O projections)
MoE(n_experts, expert_size): params = n_experts × expert_size
LayerNorm(dim):              params = 2 × dim (scale + bias)
Embedding(vocab, dim):       params = vocab × dim
```

**In practice:** Search the code for all weight-creation APIs (`tf.Variable`, `nn.Linear`, `nn.Embedding`, etc.), record shapes, and sum them up.

### 3.2 FLOPs Analysis

```
Dense layer:  FLOPs = 2 × batch × in_dim × out_dim
Attention:    FLOPs ≈ 4 × batch × seq_len² × d_model  (QKᵀ + score×V)
                     + 8 × batch × seq_len × d_model²  (QKV + O projections)
MoE:          FLOPs = (topk / n_experts) × total FLOPs of all experts
Conv1D:       FLOPs = 2 × batch × out_channels × kernel_size × in_channels × seq_len
```

**An intuition:** For a typical multi-task ranking model with a 4-layer Transformer backbone (dim=512, 32 tokens) and 40 prediction heads ([64,32,1]):
- Backbone FLOPs ≈ 4 × (8×32²×512 + 8×32×512²) ≈ ~140M
- 40 prediction heads ≈ 40 × (2×512×64 + 2×64×32 + 2×32) ≈ ~3M
- The backbone accounts for 98% of compute — but the prediction heads may take disproportionate wall-clock time due to kernel launch overhead.

### 3.3 Tensor Shape Propagation Analysis

The most practical static technique: **trace how major tensor shapes change through the graph and find where dimensions suddenly explode.**

```
Typical recommendation model data flow:

Embedding Lookup  → (B, ~2000–5000)   ← all features concatenated, very wide
  → Tokenize       → (B, N_tokens, D)  ← projected to uniform dimension
  → Backbone       → (B, N_tokens, D)  ← dimension unchanged
  → Pooling/Reduce → (B, D)            ← compress token dimension
  → Prediction heads → (B, 1) × N_tasks ← one output per task
```

Points where dimensions spike are potential bottlenecks. For example, the feature concatenation step may reach thousands of dimensions, and projecting to N_tokens × D requires substantial MatMul.

### 3.4 Graph Structure Analysis

If you have an exported compute graph (TF GraphDef, ONNX, etc.), count operator types:

```python
import tensorflow as tf

graph_def = tf.GraphDef()
with open('saved_model.pb', 'rb') as f:
    graph_def.ParseFromString(f.read())

op_counts = {}
for node in graph_def.node:
    op_counts[node.op] = op_counts.get(node.op, 0) + 1

for op, count in sorted(op_counts.items(), key=lambda x: -x[1])[:15]:
    print(f"{op}: {count}")

# Typical output:
# Const: 3000+    ← model parameters
# MatMul: 200+    ← main computation
# Add: 150+       ← residual connections, bias
# Reshape: 100+   ← shape transformations
```

If MatMul count is far above expectation (e.g., 200+), there are many small matrix multiplications that could potentially be merged.

---

## Part 4: Dynamic Profiling (Model Execution Required)

### 4.1 TensorFlow Timeline

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

tl = timeline.Timeline(run_metadata.step_stats)
with open('timeline.json', 'w') as f:
    f.write(tl.generate_chrome_trace_format())

# Open chrome://tracing/ and load timeline.json
```

### 4.2 PyTorch Profiler

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

print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=20))
prof.export_chrome_trace("trace.json")
```

### 4.3 NVIDIA nsys / Nsight Systems

GPU-level profiling:

```bash
nsys profile \
    --trace=cuda,cudnn,cublas,nvtx \
    --cuda-memory-usage=true \
    --output=serving_profile \
    python run_inference.py
# Open the .nsys-rep file with Nsight Systems GUI
```

### 4.4 How to Read a Timeline

```
Time →  0ms          5ms          10ms         15ms         20ms
CPU  │███ Preprocess ███│░│██ Schedule ██│░░░░░│█ Postprocess █│
     │                  │ │             │       │               │
GPU  │                  │░│████ Attn ████████│░│██ MLP ██│░░░│
```

**What to look for:**

1. **Long blocks** = high-cost operators; highest priority for optimization
2. **Blank gaps** = wait/scheduling overhead. Large GPU gaps → kernel launch or CPU-GPU sync bottleneck
3. **CPU-GPU overlap:** Ideally CPU prepares the next batch's features while GPU computes the current one. Serial execution means the pipeline isn't working
4. **Memory Copy events:** Large HtoD/DtoH fractions → consider pinned memory or reducing transfers

### 4.5 Take the Median Over Multiple Runs

```python
# Warmup: first N runs not counted
for _ in range(10):
    sess.run(output_tensors, feed_dict=feed_dict)

# Collect: run 100 times, report percentiles
import time, numpy as np
latencies = []
for _ in range(100):
    start = time.perf_counter()
    sess.run(output_tensors, feed_dict=feed_dict)
    latencies.append((time.perf_counter() - start) * 1000)

print(f"P50: {np.percentile(latencies, 50):.2f}ms")
print(f"P90: {np.percentile(latencies, 90):.2f}ms")
print(f"P99: {np.percentile(latencies, 99):.2f}ms")
```

---

## Part 5: Methodology for Analyzing Results

### 5.1 Bottleneck Classification

```
┌─────────────────────────────────────────────────────────────────┐
│                     Compute-Bound                               │
│  Signs: high GPU utilization, large FLOPs, compute saturated    │
│  Typical: large MatMuls, long-sequence Attention O(n²)          │
│  Fix: reduce computation — fewer layers, lower dim, pruning,    │
│       quantization, more efficient attention variants           │
├─────────────────────────────────────────────────────────────────┤
│                     Memory-Bound                                │
│  Signs: low GPU utilization, memory bandwidth saturated         │
│  Typical: Embedding Lookup, large tensor concat, gather/scatter │
│  Fix: reduce memory access — op fusion, fewer intermediate      │
│       tensors, quantize parameters                              │
├─────────────────────────────────────────────────────────────────┤
│                     Latency-Bound                               │
│  Signs: low GPU utilization, bandwidth not saturated,           │
│         large idle gaps                                         │
│  Typical: too many small ops, serial dependency chains,         │
│           RPC wait                                              │
│  Fix: op fusion, async execution, reduce op count,              │
│       batched MLP heads                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Roofline Model

The Roofline Model quantitatively determines bottleneck type using **arithmetic intensity**:

```
Arithmetic Intensity = operator FLOPs ÷ bytes of memory read/write (FLOPs/Byte)
```

```
Performance             ┌─── Compute Bound ───
(FLOPs/s)  ─────────────┤  Peak compute (A100: 312 TFLOPs bf16)
                        /│
   Memory Bound        / │
      region          /  │
─────────────────────/───┴──────────────────────
                  Ridge  Arithmetic Intensity (FLOPs/Byte)
```

**Ridge point = peak compute ÷ memory bandwidth**

For A100: 312 TFLOPs ÷ 2 TB/s ≈ **156 FLOPs/Byte**

- Intensity < 156 → Memory Bound → reduce memory access
- Intensity > 156 → Compute Bound → reduce computation

**Typical arithmetic intensities:**

```
Operator                  Intensity    Bottleneck
────────────────────────────────────────────────
Embedding Lookup          ~1           Heavily Memory Bound
Small MatMul (B=32)       ~10–30       Memory Bound
Large MatMul (B=1024)     ~200+        Compute Bound
Attention (seq=32)        ~20–50       Memory Bound
Attention (seq=1024)      ~200+        Compute Bound
LayerNorm                 ~5–10        Memory Bound
Activation (ReLU/GELU)   ~1           Memory Bound
```

**Key insight:** Recommendation models at serving time use small batch sizes, so most operators fall in the Memory Bound region. Reducing FLOPs may not reduce latency — reducing memory access (op fusion, fewer copies) is often more effective.

### 5.3 Amdahl's Law

The speedup from optimizing a module is bounded by its share of total latency:

```
Speedup = 1 / ((1 − P) + P/S)

P = fraction of total latency in the optimized module
S = speedup factor applied to that module
```

Example — backbone is 30% of latency, you speed it up 2×:
```
Speedup = 1 / (0.7 + 0.15) = 1.18×   ← only 18% faster overall
```

If feature retrieval is 50% and you eliminate it entirely:
```
Speedup = 1 / 0.5 = 2×
```

**Lesson:** Figure out the time breakdown first, then decide what to optimize. Don't start with Attention if feature retrieval takes 60% of the time.

---

## Part 6: Recommendation-Specific Considerations

### 6.1 Candidate Sharing

A ranking request typically includes N candidate items. User-side computations can be shared across all N candidates (computed once); cross features must be computed per candidate.

```
                    ┌──────────────────────┐
                    │   User-Side Compute   │  ← computed once
                    └──────────┬───────────┘
                               │ broadcast
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
        ┌──────────┐    ┌──────────┐      ┌──────────┐
        │ Cand. 1  │    │ Cand. 2  │      │ Cand. N  │  ← N times
        │  Cross   │    │  Cross   │ ...  │  Cross   │
        └──────────┘    └──────────┘      └──────────┘
```

In profiling, distinguish operators called 1× vs N×. If a shared computation is mistakenly called N times, that's a serious waste.

### 6.2 Embedding Lookup Overhead

Hundreds of feature slots, each with an embedding table on a parameter server (PS), retrieved via RPC at serving time.

```
Lookup latency = network RTT + PS query time + serialization overhead

Factors:
- Slot count (more slots → more queries)
- Embedding dimension (larger → more data transferred)
- PS load and cache hit rate
- Whether prefetch / async lookup is used
```

In the Timeline, this appears as GPU idle, waiting for CPU to feed data.

### 6.3 Multi-Task Prediction Heads

Industrial ranking models often have 30–50 prediction targets (CTR, CVR, dwell time, follow, comment, etc.), each with a small MLP head.

Each head is tiny ([256, 64, 32, 1]) but:
- There are many — total time adds up
- Each is a separate small kernel with low GPU utilization
- Kernel launch overhead may exceed actual compute time

**Optimization:** Merge MLP heads of the same structure into a single batched MatMul.

### 6.4 Write-back / Online Updates

Some models update embeddings at serving time (real-time learning, write-back). Monitor the assign graph's execution frequency, latency, and whether it contends with the inference graph for GPU resources.

---

## Part 7: Complete Profiling Checklist

### Step 1: Preparation
```
□ Define target: current P99? goal P99?
□ Confirm environment: hardware, inference framework
□ Prepare representative inputs: batch size, seq length, candidate count must match production
□ Confirm model version matches production exactly
```

### Step 2: Static Analysis
```
□ Parameter count by module
□ FLOPs by module
□ Tensor shape propagation — where do dimensions spike?
□ Op statistics — MatMul count, small op count
□ Form hypothesis: which module is expected to bottleneck?
```

### Step 3: Dynamic Profile
```
□ Warmup: 10+ iterations
□ Multi-sample: 100 iterations, P50/P90/P99
□ Collect Timeline (TF Timeline / PyTorch Profiler / nsys)
□ GPU kernel trace if applicable
□ RPC latency distribution if PS is involved
```

### Step 4: Analysis
```
□ E2E breakdown: feature retrieval / graph compute / system overhead
□ Top-10 slowest operators
□ Bottleneck classification: Compute / Memory / Latency bound?
□ Roofline: arithmetic intensity of key operators
□ Candidate sharing check: shared ops actually computed once?
□ Small op count: total kernel launch overhead?
□ Peak memory: unnecessary intermediate tensors?
□ Compare to static hypothesis — where were you wrong?
```

### Step 5: Optimize and Validate
```
□ Prioritize by Amdahl's Law: largest bottleneck first
□ Re-profile after optimization: does improvement match prediction?
□ Regression test: accuracy unchanged
□ Online A/B test: end-to-end business impact
```

---

## Part 8: Optimization Quick Reference

```
Bottleneck       Optimization                          Expected Gain
─────────────────────────────────────────────────────────────────────
Compute-Bound
                 Reduce Attention layers               Linear
                 Lower dimension (512→256)             Quadratic
                 Sequence truncation (1024→512)        Quadratic (Attn)
                 Quantization (FP32→FP16/INT8)        2–4×
                 More efficient Attention variant      Case-by-case

Memory-Bound
                 Op fusion                             Reduce load/store
                 Reduce embedding dimension            Linear
                 Use FP16/BF16 parameters             2× bandwidth
                 Embedding cache / prefetch            Fewer PS lookups
                 Eliminate unnecessary copies          Case-by-case

Latency-Bound
                 Merge MLP heads (batched MatMul)      Fewer kernels
                 XLA / TorchScript graph opt           Auto fusion
                 Async CPU-GPU pipeline                Hide wait time
                 Reduce prediction head count          Linear
                 Candidate sharing (user-side once)    N× (shared part)
```

---

## Appendix: Chrome Trace JSON Format

```json
{
  "traceEvents": [
    {
      "name": "MatMul",
      "cat": "Op",
      "ph": "X",
      "ts": 1000,
      "dur": 500,
      "pid": "GPU:0",
      "tid": "stream:0",
      "args": {
        "op": "MatMul",
        "input_shapes": "[[32,512],[512,256]]"
      }
    }
  ]
}
```

**Navigation in `chrome://tracing/`:**
- W/S: zoom in/out
- A/D: pan left/right
- Click a block: view operator details
- `/`: search by operator name
- M: mark a time range
