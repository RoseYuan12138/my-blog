---
title: "LEMUR: End-to-End Multimodal Recommendation for Douyin Search"
date: 2026-03-06
tags:
  - recommender-systems
  - multimodal
  - end-to-end training
  - Douyin
  - ByteDance
lang: en
chinese: recommender-systems/papers-reading/lemur-e2e-multimodal-rec
---

> 🌐 [中文版](./lemur-e2e-multimodal-rec.md)

Paper reading note: [LEMUR: Large scale End-to-end MUltimodal Recommendation](https://arxiv.org/abs/2511.10962) (ByteDance, 2025)

## Core Idea

Industrial multimodal recommendation systems almost universally follow a two-stage pipeline: pretrain a multimodal model, then freeze its embeddings for use in a ranking model. This paradigm has three fundamental problems: misalignment between multimodal representations and ranking objectives, inability to update multimodal features in real time, and prohibitive transmission costs for sequential multimodal embeddings. LEMUR jointly trains the multimodal encoder and ranking model end-to-end, using a Memory Bank to solve the sequential computation bottleneck — making it the first end-to-end multimodal recommendation system deployed at industrial scale.

## Problem Background

Traditional ID-based recommendation models have two inherent weaknesses: cold start (no history for new users/items) and poor generalization (high variance when behavior data is sparse). Multimodal content features can mitigate both, since they don't depend on historical interactions.

But existing industrial systems almost all use a two-stage approach:
1. Offline pretrain a multimodal model (CLIP, BLIP, etc.)
2. Freeze the embeddings and serve them as a standalone service to the ranking model

This creates four problems:
- **Representation misalignment**: Multimodal embeddings are learned on generic content tasks, not on ranking objectives (CTR)
- **ID embedding dominance**: Ranking models tend to push information into ID embeddings, leaving multimodal embeddings underfitted
- **Update frequency mismatch**: Ranking models update in real time; multimodal models stay frozen after pretraining and gradually become stale
- **Transmission bottleneck**: User history sequences with 1000+ items, each with high-dimensional embeddings, are extremely expensive to transmit online

## System Architecture

![LEMUR overall architecture: multimodal encoding, Memory Bank, sequential modeling, RankMixer ranking](./assets/lemur-architecture.png)

LEMUR consists of four core modules: **multimodal Transformer encoder**, **SQDC contrastive loss**, **Memory Bank**, and **multimodal sequential modeling**.

### 1. Multimodal Transformer Encoder

Two bidirectional Transformers encode query and document text features separately:

$$q_i = \text{Transformer}(q_\text{raw}^i)$$
$$d_i = \text{Transformer}(d_\text{raw}^i)$$

Document text includes four sources: OCR text from frames, ASR transcripts, video title, and cover image OCR. Both query and document use a `[CLS]` token whose output serves as the aggregate representation.

The key point: this Transformer is **not frozen** — it's **jointly updated with the RankMixer ranking model** via shared gradients.

### 2. SQDC: Session-masked Query-Document Contrastive

Inspired by CLIP, SQDC uses contrastive learning to align query and document representations. The standard in-batch contrastive loss is:

$$\ell_\text{contrastive} = \sum_{i, \text{label}_i=1} -\log \frac{\exp(\text{sim}(q_i, d_i) \cdot T)}{\sum_{j=0}^{K} \exp(\text{sim}(q_i, d_j) \cdot T)}$$

where $\text{sim}(q, d) = \frac{q^T d}{\|q\|\|d\|}$ is cosine similarity and $T$ is a temperature hyperparameter.

But search has a specific challenge: multiple samples in the same batch may come from the **same query (same session)** and are highly correlated. Using them as negatives for each other would destabilize training. SQDC adds session-level masking:

$$\ell_\text{SQDC} = \sum_{i, \text{label}_i=1} -\log \frac{\exp(\text{sim}(q_i, d_i) \cdot T)}{\sum_{j=0}^{K} A_{ij} \cdot \exp(\text{sim}(q_i, d_j) \cdot T)}$$

$$A_{ij} = \begin{cases} 0 & \text{if } i \neq j \text{ and } \text{QID}_i = \text{QID}_j \\ 1 & \text{else} \end{cases}$$

Samples from the same query are masked out and not used as negatives for each other.

### 3. Memory Bank

This is the key design that solves the **sequential computation bottleneck**.

**The scale problem**: With batch size 2048, the ranking model (RankMixer) uses 1.6 TFLOPs; the document Transformer uses 2.3 TFLOPs. Running the Transformer over every item in a user history sequence (1000+ items) would increase compute by 1000×.

**The solution**: During each training batch, store the current document's embedding in the Memory Bank (keyed by doc ID). When building a user's history sequence, look up embeddings from the Memory Bank — no Transformer needed.

Training spans 70 days; user history window is 1 month. The Memory Bank provides sufficient coverage.

### 4. Multimodal Sequential Modeling

![Decoder structure: cross-attention for sequence compression](./assets/lemur-decoder.png)

The history sequence $\{d_1, d_2, \ldots, d_N\}$ is compressed through a Decoder module (adapted from LONGER):

$$Q_{i+1} = \text{FFN}\bigl(\text{CrossAttention}(Q_i, d_1, d_2, \ldots, d_N)\bigr)$$

$$\text{CrossAttention}(Q_i, d_1, \ldots, d_N) = \sum_{j=1}^{N} a(Q_i, d_j) d_j$$

$$a(Q_i, d_j) = \frac{\exp(Q_i^T d_j)}{\sum_{j=1}^{N} \exp(Q_i^T d_j)}$$

A similarity module also computes cosine similarities between the target document and each item in history (plus a ranked version). Both outputs are concatenated with other features and fed into RankMixer. The longest sequence has 1000 items.

## Training Objective

Main task: binary cross-entropy (CTR prediction; positive label = watched more than 5 seconds):

$$\ell_\text{CTR} = -\frac{1}{|\mathcal{D}|} \sum_{(x,y) \in \mathcal{D}} \left[y \log \hat{y} + (1-y) \log(1-\hat{y})\right]$$

Auxiliary task: SQDC contrastive loss, jointly optimized:

$$\ell = \ell_\text{CTR} + \lambda \cdot \ell_\text{SQDC}$$

## Efficiency Optimizations

End-to-end training adds significant compute from the document Transformer. Three mitigations:

1. **Flash Attention + mixed precision**: Standard engineering speedups
2. **20% sampling**: Only 20% of samples run the full Transformer forward/backward; the rest reuse cached Memory Bank embeddings
3. **Cross-worker deduplication**: Identical documents in a batch share Transformer computation — each unique document is processed only once

At inference time, the Transformer is completely bypassed — all embeddings come from the Memory Bank.

## Experimental Results

### Offline Evaluation (Douyin Search, 3B samples, 70 days)

| Model | QAUC | ΔQAUC vs DLRM-MLP |
|---|---|---|
| DLRM-MLP (baseline) | — | — |
| RankMixer | — | +0.59% |
| LONGER | — | +0.45% |
| RankMixer + LONGER (online baseline) | — | — |
| LEMUR-SQDC | — | +0.47% vs online baseline |
| **LEMUR-SQDC-MB** | — | **+0.81% vs online baseline** |

In this industrial setting, a 0.1% QAUC improvement is considered significant enough to affect online A/B results. 0.81% is a substantial gain.

### vs Two-Stage Approach

Pretrained the same Transformer with SQDC loss on one month of data, then froze it for the downstream recommender.
**LEMUR's end-to-end training outperforms the two-stage approach by 0.69% QAUC**, validating the necessity of joint optimization.

### Online A/B Test (Douyin Search)

- 14-day A/B test: query change rate (probability of users reformulating their search query) **decreased by 0.843%**
- Statistically significant (T-test passed)
- Fully deployed; running in production for over one month

### Memory Bank Convergence

![Memory Bank staleness and coverage convergence curves](./assets/lemur-memorybank-convergence.png)

Two potential issues with the Memory Bank:
- **Staleness**: Gap between cached embeddings and current model outputs. Similarity rises from 0.92 to 0.945 and stabilizes — staleness is not a significant problem
- **Coverage**: Fraction of history items found in the Memory Bank. Current document: >98%; short sequence: ~0.95; long sequence: ~0.93 — all above 90%

### Ablation

| Configuration | ΔQAUC |
|---|---|
| LEMUR-SQDC-MB (full) | +0.81% |
| Remove Memory Bank | +0.47% (i.e., LEMUR-SQDC) |
| Remove SQDC, CTR loss only | lower |

Memory Bank contributes 0.34% additional gain. Optimal SQDC temperature is 50.

## Reflections

1. **Memory Bank is essentially an async parameter server**: The same idea as SARM's Memory Bank — avoid running the heavy model online, look up the cache instead. The difference: LEMUR's Memory Bank is written during training (current batch writes, historical batches read), while SARM's is periodically updated offline. LEMUR validates that staleness is minimal (0.95 similarity) — but it's still trading "approximate" for "real-time."

2. **SQDC vs CIC (Content-ID Contrastive)**: The paper notes that EM3's CIC loss — which aligns multimodal and ID representations — provides no benefit when the Transformer is jointly updated with the ranking model. This is interesting: the alignment loss that helps with a frozen encoder becomes redundant when training end-to-end. Joint optimization implicitly achieves alignment.

3. **Is 20% sampling enough?**: The paper provides efficiency numbers (Table 4) but no analysis of which 20% matters. Random sampling? Priority-based? The sampling strategy details deserve scrutiny.

4. **Only 4 Transformer layers**: A deliberate trade-off for latency. How much semantic depth can 4 layers of BERT-style encoding capture? Especially for short video, which is heavily visual — and LEMUR only processes text (OCR + ASR + title). What's the ceiling here?

5. **LEMUR vs SARM — the fundamental difference**: SARM uses an LLM to generate natural-language "semantic anchors" offline, then encodes them with a lightweight model. LEMUR trains a text Transformer end-to-end. SARM suits non-stationary content (live streaming); LEMUR suits large-scale search. Both solve the "multimodal-ranking decoupling" problem, just via different paths.

## References

- [LEMUR: Large scale End-to-end MUltimodal Recommendation](https://arxiv.org/abs/2511.10962) (arXiv 2511.10962)
- [RankMixer](https://arxiv.org/abs/2501.14742) (Zhu et al., 2025)
- [LONGER](https://arxiv.org/abs/2503.01375) (Chai et al., 2025)
