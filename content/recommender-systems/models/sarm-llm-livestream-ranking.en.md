---
title: "SARM: LLM Semantic Anchors for End-to-End Live-Streaming Ranking"
date: 2026-03-06
tags:
  - recommender-systems
  - live-streaming
  - LLM
  - multimodal
  - ranking
lang: en
chinese: recommender-systems/models/sarm-llm-livestream-ranking
---

> 🌐 [中文版](./sarm-llm-livestream-ranking.md)

Paper reading notes: [SARM: LLM-Augmented Semantic Anchor for End-to-End Live-Streaming Ranking](https://arxiv.org/abs/2602.09401) (Kuaishou, 2026)

## Core Idea

The challenge in live-streaming recommendation is that streamer content is real-time multimodal signal (video, audio, chat) that traditional ID-based features and discrete tags can't capture well. SARM uses MLLMs (multimodal large language models) to generate **natural-language descriptions** as "semantic anchors" for each stream, then integrates these text representations **end-to-end into the ranking model** for joint training — aligning semantic understanding directly with ranking objectives.

How this differs from prior approaches:
- **Cluster tags (SID)**: groups streamers into hundreds of categories — coarse-grained, significant information loss
- **Frozen MLLM embeddings**: embeddings don't participate in ranking training, misaligned with ranking objectives
- **SARM**: learnable text tokens as semantic anchors, jointly optimized with ranking loss

## System Architecture

The system has three layers:

```
MLLM generates semantic anchors offline (6-dimension text descriptions)
         ↓
Semantic Anchor Encoder (SAE) encodes the text
         ↓
Integrated into MMoE ranking model, end-to-end joint training
```

### Semantic Anchor Generation (Offline)

Uses Qwen2.5-VL / Qwen3-VL to generate 6 dimensions of natural-language descriptions per stream:

| Dimension | Description | Example |
|---|---|---|
| Point of Interest | Core attraction | "Singer performing live pop songs" |
| Theme | Category | "Music performance" |
| Topic | Sub-topic | "Chinese pop, covers" |
| Target Audience | Who it's for | "Young users who enjoy relaxing music" |
| Format | Content format | "Solo stream, real-time interaction" |
| Scene | Visual scene | "Indoor, warm lighting, professional mic" |

Runs offline once daily, updating all active streamers' anchors.

### Semantic Anchor Encoder (SAE)

A lightweight 4-layer BERT-style Transformer with single-head attention and RoPE positional encoding. The key designs are in the tokenizer and fusion mechanism.

#### Live-Streaming Tokenizer

Standard LLM tokenizers fragment domain-specific terms into subwords. SARM extends the tokenizer via iterative BPE: terms appearing ≥100K times in the semantic anchor corpus are merged into atomic units while preserving the general vocabulary.

#### Gated Fusion Mechanism

Rather than directly concatenating domain tokens (which degrades general semantic capability), SARM uses gated injection:

Let $h_i$ be the base tokenizer's $i$-th token embedding, $e'_i$ the corresponding domain token embedding:

$$k_i = W_K e'_i, \quad v_i = W_V e'_i$$

$$\alpha_i = \sigma\left(\frac{\text{RMSNorm}(h_i)^T \cdot \text{RMSNorm}(k_i)}{\sqrt{d}}\right)$$

$$h'_i = h_i + \alpha_i \cdot v_i$$

The gate $\alpha_i$ controls how much domain semantics to inject via attention scores. High match → large $\alpha_i$ → more injection; low match → near zero → preserves original representation.

### Author-Side Representations

SAE outputs two vectors:

**[CLS] representation** $h_{\text{CLS}}$: global semantic vector capturing stream content features.

$$h_{\text{CLS}} = \text{SAE}(\text{tokens})_{\text{[CLS]}}$$

**[TAR] representation** $h_{\text{TAR}}$: identity-aware semantic vector via cross-attention between a learnable author ID embedding $q_a$ and SAE outputs:

$$h_{\text{TAR}} = \text{CrossAttn}(q_a, H_{\text{SAE}})$$

Intuition: streamers with similar content (e.g., "outdoor fishing") have similar [CLS] vectors, but [TAR] vectors differ due to unique ID embeddings — capturing "same category, different personality" signals.

### User-Side Representation

User interest $h_{\text{UIN}}$ is built from viewing history:

1. Retrieve $h_{\text{CLS}}$ vectors of watched streamers from Memory Bank
2. Process through a Transformer layer for sequence modeling
3. Mean pooling for the final user interest vector

$$H_{\text{seq}} = \text{Transformer}([h_{\text{CLS}}^{a_1}, h_{\text{CLS}}^{a_2}, ..., h_{\text{CLS}}^{a_n}])$$

$$h_{\text{UIN}} = \text{MeanPooling}(H_{\text{seq}})$$

### Memory Bank

Maintains an author-ID-indexed cache: $M[a] = (h_{\text{CLS}}^a, h_{\text{TAR}}^a)$. Updated in real-time during training; O(1) lookup during inference.

### Ranking Model Integration

Concatenates $h_{\text{CLS}}$, $h_{\text{TAR}}$, $h_{\text{UIN}}$ with conventional ranking features into an MMoE multi-task model, jointly predicting CTR, WTR (watch time rate), LVTR (long view), and GTR (gift rate).

## Training Objectives

### Primary: Recommendation Loss

Four tasks sharing MMoE bottom layers with independent towers:

$$\mathcal{L}_{\text{rec}} = -\sum \left[ y_{\text{xtr}} \log \hat{y}_{\text{xtr}} + (1 - y_{\text{xtr}}) \log(1 - \hat{y}_{\text{xtr}}) \right]$$

where xtr ∈ {CTR, WTR, LVTR, GTR}.

### Auxiliary: Semantic Supervision

A lightweight prediction head using only $h_{\text{CLS}}$ and $h_{\text{TAR}}$:

$$\hat{y}_{\text{aux}} = \text{MLP}(\text{Concat}[h_{\text{CLS}}^a, h_{\text{TAR}}^a])$$

$$\mathcal{L}_{\text{aux}} = -y \log \hat{y}_{\text{aux}} - (1-y) \log(1 - \hat{y}_{\text{aux}})$$

### Combined

$$\mathcal{L} = \mathcal{L}_{\text{rec}} + \lambda \mathcal{L}_{\text{aux}}$$

The auxiliary task provides dense, direct supervision to semantic representations — gradients from the main ranking task must travel through MMoE and multiple tower layers, making them sparse. The auxiliary shortcut stabilizes training.

## Asymmetric Deployment

The key production design:

| | Author Side (Heavy, Offline) | User Side (Light, Online) |
|---|---|---|
| MLLM inference | Once daily, offline | Not involved |
| SAE encoding | Offline, stored in Memory Bank | Lookup from Memory Bank |
| Inference latency | No online impact | Constant-time lookup |
| Update frequency | Daily | Real-time (streaming continuous training) |

All heavy computation (MLLM + SAE) happens offline. Online inference only requires O(1) Memory Bank lookups by author ID. User-side Transformer encoding is identical in training and inference — no train-serve skew.

## Experimental Results

### Offline Metrics (Base Model: HoME)

Step-by-step component ablation:

| Method | CTR AUC | CTR GAUC | WTR AUC | WTR GAUC | LVTR AUC | LVTR GAUC | GTR AUC | GTR GAUC |
|---|---|---|---|---|---|---|---|---|
| Base | 0.8387 | 0.6453 | 0.9217 | 0.6500 | 0.8928 | 0.7542 | 0.9792 | 0.7319 |
| + Tags | 0.8390 | 0.6457 | 0.9220 | 0.6510 | 0.8932 | 0.7542 | 0.9794 | 0.7324 |
| + SIDs | 0.8389 | 0.6469 | 0.9221 | 0.6536 | 0.8936 | 0.7553 | 0.9799 | 0.7324 |
| + MLLM Emb (MMBee) | 0.8385 | 0.6451 | 0.9210 | 0.6475 | 0.8932 | 0.7551 | 0.9790 | 0.7320 |
| + MLLM Emb (SIM) | 0.8394 | 0.6463 | 0.9224 | 0.6509 | 0.8939 | 0.7548 | 0.9792 | 0.7330 |
| + SAE (Author) | 0.8396 | 0.6475 | 0.9225 | 0.6511 | 0.8948 | 0.7567 | 0.9804 | 0.7342 |
| + Aux Loss | 0.8398 | 0.6474 | 0.9227 | 0.6513 | 0.8948 | 0.7573 | 0.9803 | 0.7352 |
| + User Sequence | 0.8405 | 0.6483 | 0.9227 | 0.6519 | 0.8955 | 0.7575 | 0.9816 | 0.7358 |
| **SARM (Full)** | **0.8411** | **0.6485** | **0.9232** | **0.6522** | **0.8959** | **0.7580** | **0.9825** | **0.7369** |

Key observations:
- **Frozen MLLM embedding (MMBee) performs worse than Base** — validates that semantic representations not trained with ranking are useless
- **SIDs beat Tags on GAUC** — cluster IDs are more useful than sparse tags for personalized ranking
- **Aux Loss mainly boosts GTR (+0.28% GAUC)** — gifting is the sparsest signal, auxiliary supervision helps most

### Gated Fusion Ablation

| [CLS] Encoding | CTR AUC Δ | CTR GAUC Δ | LVTR AUC Δ | LVTR GAUC Δ |
|---|---|---|---|---|
| Base Tokenizer | +0.07% | +0.10% | +0.10% | +0.08% |
| Live-Streaming Tokenizer only | +0.06% | +0.06% | +0.08% | +0.06% |
| **Gated Fusion** | **+0.09%** | **+0.14%** | **+0.12%** | **+0.22%** |

Using the domain tokenizer alone is actually worse than the base tokenizer (general semantic capability degraded). Gated fusion gets the best of both.

### [TAR] Identity-Aware Representation Ablation

| Aggregation | CTR AUC Δ | CTR GAUC Δ | LVTR AUC Δ | LVTR GAUC Δ |
|---|---|---|---|---|
| Mean Pooling | +0.04% | +0.07% | +0.10% | +0.13% |
| **Cross-Attention** | **+0.09%** | — | **+0.22%** | **+0.25%** |

Cross-Attention shows significantly larger gains on LVTR and GAUC — identity awareness matters more for personalized long-term retention.

### User Sequence Ablation

| Sequence vector | CTR AUC Δ | LVTR AUC Δ |
|---|---|---|
| [TAR] sequence | +0.15% | +0.28% |
| **[CLS] sequence** | **+0.18%** | **+0.30%** |

Using [CLS] (content semantics) rather than [TAR] (identity semantics) for user interest sequences works better — user interests are driven more by content type than specific streamer identity.

### Long-Tail Streamer Analysis

Tested across exposure buckets: [0-60), [60-100), [100-1K), [1K-10K), [10K-∞). SARM shows the largest relative GAUC gains for low-exposure streamers. This makes sense: popular streamers already have abundant behavioral data where ID features suffice; long-tail streamers have sparse behavior, so semantic anchors' content understanding helps most.

### Online A/B Test (Kuaishou + Kuaishou Lite, 2 weeks)

| Platform | Exposure | Watch Count | Watch Time | Click | Gift | Effective View | Follow |
|---|---|---|---|---|---|---|---|
| Kuaishou | +0.424% | +0.189% | +0.092% | +0.982% | +0.482% | +0.070% | +0.805% |
| Kuaishou Lite | +1.190% | +0.397% | +0.962% | +0.562% | +1.287% | +0.340% | +0.522% |

Kuaishou Lite shows larger gains, likely because its user base relies more heavily on recommendations (vs. main app users who search and follow more actively).

### MLLM Quality Sensitivity

| MLLM | Benchmark Score | CTR AUC Δ | CTR GAUC Δ | LVTR AUC Δ | LVTR GAUC Δ |
|---|---|---|---|---|---|
| Qwen2.5-VL-7B | 2.308 | +0.19% | +0.20% | +0.27% | +0.22% |
| **Qwen3-VL-8B** | 2.519 | **+0.24%** | **+0.32%** | **+0.31%** | **+0.38%** |

Better MLLM → better anchors → better ranking. No architecture changes needed — just swap in a stronger MLLM.

### Computational Cost

| Resource | Training Overhead | Inference QPS Drop | Per-Query Latency |
|---|---|---|---|
| CPU | +3.02% | -3.4% | +2% |
| GPU | +2.75% | — | — |

Negligible overhead. Production-ready.

## Attention Visualization

Figure 7 in the paper shows [CLS] attention weights over different tokens. For beauty streamers, high-weight tokens concentrate on "appearance," "skincare," "interaction"; for music streamers, on "singer," "performance," "atmosphere." The semantic anchors learn discriminative content understanding rather than collapsing to uniform representations.

## Reflections

1. **The 6 semantic dimensions are manually designed** — what if the dimensions don't cover all important aspects? The paper doesn't discuss dimension selection sensitivity.
2. **Daily anchor updates** — for rapidly changing streams (e.g., streamer switches topics mid-session), is daily granularity sufficient? Could incremental updates help?
3. **Gated Fusion is essentially side information injection** — this pattern isn't limited to live-streaming; any scenario with rich side information that shouldn't corrupt the main representation space could benefit.
4. **The auxiliary loss design is elegant** — adding direct supervision to intermediate representations to solve long-path gradient sparsity is a general technique for deep model training.
5. **"Better MLLM = better ranking"** means SARM's ceiling depends on MLLM capability — as MLLMs improve, the ranking model automatically benefits. This is a good architectural property.

## References

- [SARM: LLM-Augmented Semantic Anchor for End-to-End Live-Streaming Ranking](https://arxiv.org/abs/2602.09401)
- [Qwen2.5-VL](https://arxiv.org/abs/2412.14135)
- [MMoE: Modeling Task Relationships in Multi-Task Learning](https://dl.acm.org/doi/10.1145/3219819.3220007)
