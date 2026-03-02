---
title: "Debugging NaN in Model Training: Tracing the Root Cause Through 18MB of Logs"
date: 2026-03-01
tags:
  - machine learning
  - debugging
  - MoE
  - training stability
lang: en
chinese: machine-learning/debugging/nan-debug-moe-training
---

> 🌐 [中文版](./nan-debug-moe-training.md)

> Training loss suddenly goes NaN — is it gradient explosion or forward overflow? Here's how I traced the root cause through 18MB of debug logs, step by step.

## The Problem

While training a recommendation model with MoE (Mixture of Experts), two workers simultaneously reported NaN after running for a while. The logs came from the framework's `DebugTensorMaxNorm` traceback — one per worker, 18MB each, nearly 30,000 lines.

Opening the logs: walls of `[nan]`. The gut reaction was "gradient explosion" — but was that actually the case?

## Understanding the Log Format

Before diving in, understand the log structure:

```
[DebugTensorMaxNorm][Backtrace_N <trace_target>] [<op_name>:<output_index>] [<max_norm_value>]
```

Three key fields:

- **`Backtrace_N`**: Trace depth. `N=0` is the final output (e.g., `total_loss`), larger N means deeper in the computation graph. Think of it as: `Backtrace_0` is the "effect", `Backtrace_N` is the "cause".
- **`trace_target`**: What's being traced. `total_loss` is the forward pass chain, `raw_dense_grad` is the gradient chain, `sparse_norm_square` is the gradient norm of sparse parameters.
- **`max_norm_value`**: Max norm of the tensor. Normal = finite number, abnormal = `nan` or `inf`.

With this structure clear, the debugging strategy becomes obvious: **trace along Backtrace from shallow to deep, find the first operator that "goes bad"**.

---

## Step 1: Partition — Does NaN Start in Forward or Backward?

With 30,000 lines of logs, the first move is **partition search**, not line-by-line reading.

NaN has two possible origins:
- **Forward pass**: An operator's output overflowed (activation values too large)
- **Backward pass**: Gradient explosion

A quick grep tells us:

```bash
# Search for anomalies in forward pass
grep -n "total_loss.*\[nan\]\|total_loss.*\[inf\]" traceback.log | head -20

# Search for anomalies in backward pass
grep -n "raw_dense_grad.*\[nan\]\|raw_dense_grad.*\[inf\]" traceback.log | head -20
```

Results:

```
# Forward pass
[Backtrace_0 total_loss] [add_223:0] [nan]
...
[Backtrace_16 total_loss] [logistic_loss_77:0] [nan]
[Backtrace_16 total_loss] [InterFusion_output_1/Mean:0] [inf]  ← Note: inf, not nan
```

**Key finding**: The forward pass contains not just `nan`, but also `inf`.

This immediately changes the direction — **if it were pure gradient explosion, the forward pass should show all normal values**. Forward `inf` means the problem originated in the forward pass; the gradient `nan` is just a downstream consequence.

> **Rule of thumb**: `inf` is more informative than `nan`. `nan` can arise from various operations (0/0, inf-inf, etc.), but `inf` typically means numeric overflow — much more specific.

---

## Step 2: Trace the `inf` Chain — Find the First Overflow Operator

Since forward has `inf`, trace it deeper. **Find the `inf` with the largest Backtrace_N — that's the first point of overflow.**

```bash
grep -n "\[inf\]" traceback.log
```

Very clear results:

```
Backtrace_15 → [concat_47:0] [inf]
Backtrace_16 → [InterFusion_output_1/Mean:0] [inf]
Backtrace_17 → [InterFusion_layer_3/add_1:0] [inf]
Backtrace_18 → [InterFusion_layer_3/.../mlp_1/add:0] [inf]
Backtrace_19 → [InterFusion_layer_3/.../sparse_mo_e_4/Reshape_6:0] [inf]
Backtrace_20 → [InterFusion_layer_3/.../sparse_mo_e_4/MoeGatherForward:0] [inf]
Backtrace_21 → [InterFusion_layer_3/.../down_1/MoeGroupedGemmForward:0] [inf]  ← deepest!
```

**Pinpointed**: `Backtrace_21`'s `MoeGroupedGemmForward` (the down projection matrix multiply in the MoE Expert) is the first operator producing `inf`.

---

## Step 3: Check the Operator's Inputs — Why Did GEMM Overflow?

`MoeGroupedGemmForward` is a matrix multiply (GEMM). GEMM overflow means either weights are too large or input activations are too large.

```bash
grep "InterFusion_layer_3.*mlp" traceback.log | grep "Backtrace_2[1-3]"
```

```
# Context around the inf operator (Backtrace_21)
InterFusion_layer_3/.../mlp_share/mul          → 24,976   ← activations already huge!
InterFusion_layer_3/.../MLP_down_1/kernel      → 1.98     ← weights are normal
InterFusion_layer_3/.../MLP_down_1/MatMul      → 12,676   ← shared MLP output
InterFusion_layer_3/.../ln2_1/moments/variance → 53,593
```

The truth emerges:

- **Weights are fine** (kernel MaxNorm ~2.0) — not weight explosion
- **Input activations reached 24,976** — this is the root cause
- LayerNorm variance at 53,593 — the numerical distribution of this layer has completely gone haywire

---

## Step 4: Cross-Layer Comparison — Isolated Issue or Systemic Growth?

| InterFusion Layer | Shared MLP Output MaxNorm | MoE Expert Output MaxNorm |
|:-----------------:|:-------------------------:|:-------------------------:|
| layer_0           | 979                       | 23                        |
| layer_1           | 1,402                     | 60                        |
| layer_2           | 993                       | 54                        |
| **layer_3**       | **12,676**                | **inf**                   |

Layers 0–2 have shared MLP outputs around ~1,000, but **layer_3 jumps to 12,676 — more than 10x the other layers**. This doesn't look like uniform growth across layers; it looks like layer_3 has some kind of amplification effect causing activations to blow up specifically there.

---

## Step 5: Verify the inf → nan Causal Chain

```
Backtrace_22:
[Mul_476:0]              → [-inf]   ← inf negated to -inf
[logistic_loss_71:0]     → [nan]    ← log(1 + exp(-inf)) produces nan
[logistic_loss_73/Exp:0] → [nan]    ← exp(nan) = nan, starts spreading
```

**The propagation chain is exact**:

```
MoE down projection outputs inf
  → InterFusion_layer_3 outputs inf
  → Model final output is inf
  → logistic_loss(inf) = nan
  → All gradients become nan
```

---

## Step 6: Confirm No Independent Gradient Issue

Gradient `nan` appears exactly at `Backtrace_22`, perfectly aligned with the forward pass timeline. **There's no independent source of nan on the gradient side** — it's purely the forward nan propagating back.

---

## Root Cause Summary

```
Root cause: The MoE Expert (sparse_mo_e_4) down projection
            (MoeGroupedGemmForward) in InterFusion_layer_3 overflows to inf

Reason: The shared MLP activations in this layer ballooned to 24,976
        (other layers ~1,000). After MoE expert matrix multiply,
        the value exceeds floating point range → inf

Essence: Not a sudden gradient explosion. Forward activations gradually
         inflated during training. InterFusion_layer_3 was the worst,
         eventually breaking the floating point ceiling at some step.
```

---

## Debugging Methodology: Partition, Trace Deep, Compare Wide

```
Partition: Separate forward vs. backward, determine which stage NaN originates from
  ↓
Trace Deep: Follow Backtrace from shallow to deep, find the first inf/nan operator
  ↓
Investigate: Check the operator's inputs — weight problem or activation problem?
  ↓
Compare Wide: Cross-compare same-type operators across layers — isolated or systemic?
  ↓
Verify: Confirm the nan propagation causal chain, rule out independent nan sources
```

**Practical tips**:

1. **Search `inf` before `nan`**. `inf` is far more informative — it explicitly says "numeric overflow"
2. **Watch the Backtrace number**. Largest number = deepest anomaly in the computation graph = closest to root cause
3. **Separate weights from activations**. Normal weights but exploding activations = cumulative effect from earlier layers, not the current layer's parameters
4. **Cross-compare same-type operators**. You can't tell if a value is abnormal without comparing it to the same operator in other layers
5. **When forward has inf/nan, don't rush to look at gradients**. Trace the forward chain first — gradients are almost certainly just downstream effects

---

## Possible Fixes

- Add activation clipping to MoE expert outputs
- Review LayerNorm epsilon in InterFusion_layer_3 (currently `1e-6`, which is meaningless when variance=53,593)
- Add gradient clipping to prevent weights from continuously growing
- Monitor per-layer activation MaxNorm and intervene early (e.g., dynamically reduce learning rate)
- Consider adding post-norm or activation scaling between InterFusion layers
