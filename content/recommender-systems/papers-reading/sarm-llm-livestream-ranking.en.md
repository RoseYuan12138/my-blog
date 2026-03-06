---
title: "SARM: End-to-End Live-Streaming Ranking with LLM Semantic Anchors"
date: 2026-03-06
tags:
  - recommender-systems
  - live-streaming
  - multimodal
  - LLM
  - Kuaishou
lang: en
chinese: recommender-systems/papers-reading/sarm-llm-livestream-ranking
---

> 🌐 [中文版](./sarm-llm-livestream-ranking.md)

Paper reading note: [LLM-Augmented Semantic Anchor for End-to-End Live-Streaming Ranking](https://arxiv.org/abs/2602.09401) (Kuaishou Technology, 2026)

## Core Idea

Live-streaming recommendation faces non-stationary content semantics. Existing approaches either compress semantics into discrete tags (information bottleneck) or extract dense embeddings independently (misaligned with ranking objectives). SARM embeds LLM-generated natural-language descriptions — "semantic anchors" — directly into ranking optimization, enabling end-to-end joint training of semantic understanding and ranking. A lightweight encoder and asymmetric deployment strategy keep latency under control.

## Problem Background

![Comparison of three semantic representation approaches: discrete abstraction, dense embeddings, SARM semantic anchors](./assets/sarm-semantic-comparison.png)

Live-streaming poses unique challenges:

- **Non-stationary semantics**: Content changes minute by minute — no time for offline pre-analysis like with short videos
- **Strict latency requirements**: Real-time serving with no tolerance for large model inference
- **Cold start**: New streamers have no behavioral history; content signals must carry the load

Limitations of existing approaches:

1. **Discrete semantic abstractions** (Tags / Semantic IDs): Cluster or RQ-VAE compress multimodal content into a finite vocabulary. Interpretable, but the **discrete bottleneck** is unavoidable — fine-grained semantics get lost
2. **Dense multimodal embeddings**: Preserve high-dimensional semantics, but extracted independently and weakly aligned with ranking objectives — and deploying large encoders online is prohibitively expensive

The shared problem: **content understanding and ranking optimization are decoupled by an intermediate layer, preventing end-to-end training**.

## System Architecture

![SARM overall architecture: semantic anchor generation → SAE encoding → Memory Bank → ranking model](./assets/sarm-architecture.png)

SARM consists of three core components: **Semantic Anchors**, **Semantic Anchor Encoder (SAE)**, and an **end-to-end ranking model**.

### 1. Semantic Anchors

A fine-tuned MLLM (based on Qwen-VL series) generates structured natural-language descriptions for each streamer **offline**. Three input modalities:

- **Visual keyframes**: ~20 dynamically sampled frames per stream, prioritizing close-up faces and representative scenes
- **Audio transcription**: ASR within fixed temporal windows aligned with sampled keyframes
- **User comments**: Filtered by engagement value; top 32 representative comments retained

Generated anchors cover six dimensions: **POI, Theme, Topic, Target Audience, Format, Scene**.

Formally, a streamer $\mathbf{s}$'s semantic anchor is a token sequence:

$$A_s = \{t_1, t_2, \ldots, t_n\}$$

Key design: anchor tokens are not frozen external features — they are **learnable parameters jointly optimized within the ranking loss**, updated by ranking gradients. This is the fundamental departure from SIDs and dense embeddings.

### 2. Semantic Anchor Encoder (SAE)

![SAE gated fusion module in detail](./assets/sarm-gated-fusion.png)

Using a large LLM as the encoder is too slow. But small models have a concrete problem: live-streaming domain terms (e.g., "Lao Tie", "PUBG") get fragmented by general-purpose tokenizers, and lightweight models can't reconstruct the semantics from subword pieces.

SAE's solution: **dual-token gated fusion**.

#### Live-Streaming Tokenizer

Run BPE merging on historical anchor corpora to merge frequently co-occurring terms into atomic tokens:

$$\text{PUBG} \rightarrow (t_1, t_2, t_3) = ({\rm P}, {\rm UB}, {\rm G}) \quad \xrightarrow{\text{BPE}} \quad \text{[PUBG]}$$

Merge threshold: 100k occurrences. Incrementally updated daily.

#### Gated Fusion

Two token sequences processed in parallel: the base LLM encodes the original sequence to get hidden states $h_i$; the domain tokenizer encodes the augmented sequence to get embeddings $e_i$. Learnable gates fuse them:

$$\bm{k}_i = \mathbf{W}_K \bm{e}_i, \quad \bm{v}_i = \mathbf{W}_V \bm{e}_i$$

$$\alpha_i = \sigma\!\left(\frac{\text{RMSNorm}(\bm{h}_i)^\top \text{RMSNorm}(\bm{k}_i)}{\sqrt{d}}\right)$$

$$\bm{h}'_i = \bm{h}_i + \alpha_i \cdot \bm{v}_i$$

The scalar gate $\alpha_i$ controls how much domain semantics to inject at each position — **on-demand fusion** rather than hard replacement, preserving the base model's general language understanding.

#### Lightweight Backbone

4-layer BERT-style encoder with single-head attention and RoPE. The `[CLS]` token provides the aggregated representation $h_\text{CLS}$.

To model both content semantics and streamer identity signals, an explicit author ID embedding is fused via cross-attention:

$$\bm{h}^\text{a}_\text{TAR} = \text{CrossAttention}(\bm{h}^\text{a}_{id}, \bm{h}, \bm{h})$$

### 3. End-to-End Ranking Model

**Author side**: $h^a_\text{CLS}$ (semantics) + $h^a_\text{TAR}$ (identity-aware)

**User side**: Retrieve historical streamer embeddings from Memory Bank, apply Transformer + MeanPooling:

$$\bm{h}^u_\text{UIN} = \text{MeanPooling}\big(\text{Transformer}(\bm{h}^u)\big)$$

Concat into the existing multi-task ranking backbone:

$$\hat{y} = \text{MultiTask}\bigl(\text{Concat}[h^a_\text{CLS},\, h^a_\text{TAR},\, h^u_\text{UIN},\, h_\text{rank}]\bigr)$$

## Training Objectives

Main task: multi-objective BCE over multiple engagement signals (CTR, WTR, LVTR, GTR, etc.):

$$\mathcal{L}_\text{rec} = -\sum_{\text{xtr}}^{\text{Tasks}} \Bigl(y^\text{xtr} \log \hat{y}^\text{xtr} + (1 - y^\text{xtr}) \log(1 - \hat{y}^\text{xtr})\Bigr)$$

Auxiliary task: a lightweight CTR prediction head directly supervises the semantic representation:

$$\hat{y}_\text{aux} = \text{MLP}(\text{Concat}[h^a_\text{CLS}, h^a_\text{TAR}])$$

$$\mathcal{L}_\text{aux} = -y \log \hat{y}_\text{aux} - (1 - y) \log(1 - \hat{y}_\text{aux})$$

Final loss:

$$\mathcal{L} = \mathcal{L}_\text{rec} + \lambda \mathcal{L}_\text{aux}$$

The auxiliary loss provides direct ranking supervision to the semantic representations, preventing the optimization mismatch between semantic space and ranking space from destabilizing training.

## Experimental Results

### Offline Comparison (Kuaishou dataset, 400M users + 3M streamers)

| Model | CTR AUC | CTR GAUC | WTR AUC | WTR GAUC | LVTR AUC | LVTR GAUC | GTR AUC | GTR GAUC |
|---|---|---|---|---|---|---|---|---|
| Base | 0.8387 | 0.6453 | 0.9217 | 0.6500 | 0.8928 | 0.7542 | 0.9792 | 0.7319 |
| +Tags | 0.8390 | 0.6457 | 0.9220 | 0.6510 | 0.8932 | 0.7542 | 0.9794 | 0.7324 |
| +SIDs | 0.8389 | 0.6469 | 0.9221 | 0.6536 | 0.8936 | 0.7553 | 0.9799 | 0.7324 |
| +MLLM Emb | 0.8385 | 0.6451 | 0.9210 | 0.6475 | 0.8932 | 0.7551 | 0.9790 | 0.7320 |
| **SARM** | **0.8411** | **0.6485** | **0.9232** | **0.6522** | **0.8959** | **0.7580** | **0.9825** | **0.7369** |

Notable observations:

- MLLM Embedding actually underperforms Base on CTR and WTR — confirming the "dense embeddings misaligned with ranking" hypothesis
- Semantic IDs show decent GAUC gains but limited AUC improvement — discretization loses cross-category fine-grained distinctions
- SARM leads across all 8 metrics; GTR GAUC +0.50% is highly significant in industrial settings

### Ablation

| Replaced Component | CTR AUC Δ | CTR GAUC Δ | LVTR AUC Δ | LVTR GAUC Δ |
|---|---|---|---|---|
| Standard Tokenizer replacing Live Tokenizer | +0.07% | +0.10% | +0.08% | +0.11% |
| Removing Gated Fusion | +0.09% | +0.14% | +0.12% | +0.22% |
| Removing Cross Attention | +0.09% | +0.22% | +0.20% | +0.25% |
| [CLS] Sequence replacing full approach | +0.18% | +0.30% | +0.27% | +0.33% |

Removing identity-aware Cross Attention has the largest GAUC impact (+0.22%/+0.25%), confirming that individual-level representations are critical for ranking.

### Online A/B Tests

| Platform | Exposure | Watch Count | Watch Time | Click | Gift | Effective View | Follow |
|---|---|---|---|---|---|---|---|
| Kuaishou | +0.424% | +0.189% | +0.092% | +0.982% | +0.482% | +0.070% | +0.805% |
| Kuaishou Lite | +1.190% | +0.397% | +0.962% | +0.562% | +1.287% | +0.340% | +0.522% |

Fully deployed **serving 400M+ daily active users**. Kuaishou Lite shows larger gains, possibly because its users are more sensitive to recommendation quality.

### Computational Overhead

| Metric | Base | SARM |
|---|---|---|
| CPU Usage | 48.69% | 51.71% |
| GPU Usage | 77.54% | 80.29% |
| Training Time | 1.00x | 1.08x |
| QPS | 280.71 | 271.30 |
| Inference Latency | 1.00x | 1.02x |

+8% training overhead, only +2% inference latency — asymmetric deployment keeps heavy author-side computation entirely offline.

## Asymmetric Deployment

![SARM asymmetric deployment pipeline: Memory Bank for low-latency online serving](./assets/sarm-deployment.png)

The Memory Bank caches each streamer's encoded representations: $\mathcal{M}[a] = (h^a_\text{CLS}, h^a_\text{TAR})$.

- **Offline**: SAE periodically re-encodes streamers and updates the Memory Bank
- **Online**: Constant-time lookup — SAE doesn't participate in real-time inference

This resolves the core tension between "rich semantic model" and "strict serving latency."

## Case Study

![Semantic anchor attention heatmaps and similar streamer retrieval](./assets/sarm-case-study.png)

Attention visualization on two streamers with different styles: the model correctly focuses on discriminative tokens (game titles, audience descriptors) and retrieves semantically similar streamers based on anchor representations. The anchors are learning meaningful content semantics, not random patterns.

## Reflections

1. **Semantic anchors vs SIDs — the fundamental difference**: SIDs compress semantics into a finite vocabulary (information bottleneck is unavoidable); semantic anchors use open-ended natural-language tokens (theoretically lossless). But can a 4-layer lightweight SAE actually leverage all that information? That's an open question.

2. **MLLM generation quality as the ceiling**: The entire system's upper bound depends on the offline MLLM's anchor quality. The paper mentions domain-specific fine-tuning but is vague about generation quality evaluation. What happens when the anchors are wrong?

3. **Memory Bank staleness**: Live-streaming content changes daily (gaming today, lifestyle tomorrow), but the Memory Bank is updated asynchronously. How much lag is there? Does this hurt rapidly-evolving streamers or new entrants?

4. **Domain tokenizer transferability**: BPE-extended tokenizers should work equally well in other vertical domains (medical, legal, finance) — all have domain-specific terms that general tokenizers fragment. Worth exploring.

5. **Cold start — really solved?** The paper claims semantic anchors help cold start, but the experiments don't include a dedicated cold-start evaluation. For a brand-new streamer with no behavioral history at all, are anchors alone sufficient?

## References

- [LLM-Augmented Semantic Anchor for End-to-End Live-Streaming Ranking](https://arxiv.org/abs/2602.09401) (arXiv 2602.09401)
