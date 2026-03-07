---
title: "LEMUR / Cotrain: End-to-End Multimodal Recommendation at Douyin Scale"
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

> Internal name: **Cotrain**. Deployed in Douyin Search and e-commerce.

## Core Idea

Industrial multimodal recommendation systems almost universally follow a two-stage pipeline: pretrain a VLM, freeze its embeddings, feed them into a DLRM. The fundamental problem: **VLM can't perceive real user feedback**. I2I-based fine-tuning learns group-level preferences, which in a personalized recommendation setting means the same model for everyone ("one face for a thousand people") instead of truly personalized representations.

LEMUR / Cotrain jointly trains the multimodal encoder and ranking model end-to-end, letting the VLM directly receive gradients from the DLRM, while using a Memory Bank to solve the sequential computation bottleneck — the first end-to-end multimodal recommendation system deployed at industrial scale.

## Problem Background

The ByteDance team attempted a similar direction as early as **2022**, but couldn't launch due to compute and architecture constraints at the time.

As UGC and long-tail content grew on Douyin, the cold-start limitations of ID-based systems became increasingly apparent — collaborative filtering depends on historical interactions, so new content inherently suffers from traffic efficiency problems. The evolution of multimodal in recommendation went roughly:

> VL model → visual tags → VLM embeddings as DLRM features → I2I behavior fine-tuned VLM

Yet no matter how much fine-tuning data was added or how large the VLM got, the **two-stage training paradigm** faced two core challenges:

**1. VLM cannot perceive real user feedback**

I2I fine-tuning (SwingI2I, etc.) fundamentally aggregates group preferences. Without joint training with the downstream DLRM, the VLM learns a "one-size-fits-all" representation — "one face for a thousand people" — instead of individually personalized ones.

**2. Two-stage iteration pipelines are complex and slow**

Data preparation → supervised fine-tuning → model launch → full retrospective → offline evaluation → production deployment — every iteration requires the full pipeline, creating high maintenance costs and long iteration cycles.

Additional challenges: each user sequence has hundreds to thousands of history items, making real-time VLM inference over full sequences infeasible; at large batch sizes, simply transmitting image and text data can saturate GPU network bandwidth.

## System Architecture

![LEMUR overall architecture: multimodal encoding, Memory Bank, sequential modeling, RankMixer ranking](./assets/lemur-architecture.png)

The design inspiration comes from **Memory Bank in visual self-supervised learning (SSL)** — the bottleneck of "hundreds of items in user sequences causing compute explosion" is structurally similar to "massive negative samples needed in contrastive learning," and both draw candidate sets from historical positives.

### 1. Multimodal Transformer Encoder

Two bidirectional Transformers encode query and document text features separately:

$$q_i = \text{Transformer}(q_\text{raw}^i), \quad d_i = \text{Transformer}(d_\text{raw}^i)$$

Document text covers: OCR, ASR transcripts, video title, cover image OCR. Key: the Transformer **jointly updates gradients with RankMixer** — not frozen.

### 2. SQDC: Session-masked Query-Document Contrastive

Inspired by CLIP, SQDC uses contrastive learning to align query and document representations. In search, a batch may contain multiple samples from the same query — highly correlated but not suitable as negatives for each other. Session-level masking handles this:

$$\ell_\text{SQDC} = \sum_{i, \text{label}_i=1} -\log \frac{\exp(\text{sim}(q_i, d_i) \cdot T)}{\sum_{j} A_{ij} \cdot \exp(\text{sim}(q_i, d_j) \cdot T)}$$

$$A_{ij} = \begin{cases} 0 & i \neq j \text{ and } \text{QID}_i = \text{QID}_j \\ 1 & \text{otherwise} \end{cases}$$

**Key design: False Negative masking.** Samples that were "exposed but not clicked, without negative feedback" are masked in the loss — leveraging domain-specific behavioral signals to avoid treating genuinely interesting items as negatives. This is something generic VLM contrastive learning can't do.

Search uses a Query-to-Item task; recommendation uses an Item-to-Item task. Both follow the same SQDC framework.

### 3. Memory Bank

![LEMUR staleness and coverage convergence curves](./assets/lemur-memorybank-convergence.png)

This solves the sequential computation bottleneck.

**Training (three steps):**
1. **Dedup + distribute**: Deduplicate candidate video pool (leveraging the heavy-tail effect), distribute evenly across GPU Ranks
2. **VLM inference + All Gather**: Each Rank runs VLM forward on its assigned videos, then All Gather syncs to all Ranks
3. **Write to Memory Bank**: Latest VLM embeddings overwrite the cache in real time

**Serving:** Directly read from Memory Bank. No VLM involved in real-time inference. Online Learning streaming training updates the Memory Bank asynchronously.

**High-frequency content sampling:** Due to heavy-tail dynamics, popular content gets updated frequently while long-tail content may have embeddings from hundreds of steps ago (staleness imbalance). As the VLM converges, popular content updates with only **10% probability** — otherwise using cached values. This saves ~**50% of compute**.

### 4. Multimodal Sequential Modeling

![Decoder structure: cross-attention for sequence compression](./assets/lemur-decoder.png)

History sequence $\{d_1, \ldots, d_N\}$ compressed through Decoder (adapted from LONGER):

$$Q_{i+1} = \text{FFN}\bigl(\text{CrossAttention}(Q_i, d_1, \ldots, d_N)\bigr)$$

A similarity module also computes cosine similarities between the target document and each history item. Longest sequence: 1000 items.

## Training Objective

$$\ell = \ell_\text{CTR} + \lambda \cdot \ell_\text{SQDC}$$

The auxiliary SQDC loss directly supervises the semantic representations, preventing misalignment between VLM and DLRM optimization directions.

## Experimental Results

### Offline Comparison (Douyin Search, 3B samples, 70 days)

| Model | ΔQAUC vs online baseline |
|---|---|
| RankMixer | +0.59% |
| LONGER | +0.45% |
| LEMUR-SQDC | +0.47% |
| **LEMUR-SQDC-MB (full)** | **+0.81%** |

A 0.1% QAUC improvement is sufficient to affect online A/B results in this setting.

### vs Two-Stage Approach

Compared against a two-stage approach using Q2D (Query-to-Document) fine-tuned VLM (frozen, used for downstream recommendation). **LEMUR's end-to-end training still shows substantial gains** — even when the VLM is specifically fine-tuned for the search task, joint optimization adds irreplaceable value.

### Online A/B Tests

- **Douyin Search**: 14-day A/B, query change rate down **0.843%**, T-test significant, fully deployed for 1+ month
- **E-commerce**: Significant offline and online gains across multiple metrics, deployed

Cotrain has become **one of ByteDance's main paradigms for multimodal × recommendation**.

### Staleness and Coverage

- **Staleness**: Similarity between cached and current model output rises from 0.92 to 0.945 and stabilizes — manageable overall
- **Staleness imbalance**: Popular content gets fresh embeddings (a few steps old); long-tail content may have embeddings hundreds of steps old. Mitigated by 10% update probability for popular content, saving 50% compute
- **Coverage**: Current document > 98%; short sequence ~0.95; long sequence ~0.93 — all above 90%

## Reflections

1. **"One face for a thousand" vs personalization**: I2I fine-tuning learns co-click signals at the group level — fundamentally, it learns content similarity, not individual preference. Joint training lets the VLM learn from user-level CTR signals. But even LEMUR's batch-level CTR signals are still group behavior — truly individual personalization needs more.

2. **Staleness imbalance as a systematic bias**: This isn't just a mean staleness problem. The model trains head content with fresh embeddings and long-tail content with stale ones — a systematic asymmetry that may cause head content representations to overfit while long-tail representations lag.

3. **False Negative masking as domain advantage**: "Exposed but not clicked" in recommendation ≠ disliked. The user might not have scrolled there, or was interested but busy. Using domain behavioral signals (presence or absence of negative feedback) to distinguish these samples is something generic contrastive learning frameworks can't do — this is proprietary domain knowledge materialized in training signal.

4. **Currently using lightweight SigLip; planning Seed 1.6 36B**: Scaling to large parallel-trained VLMs is the next challenge. Will the jump from lightweight to large VLM bring qualitative improvement, or diminishing returns? Architecture and resource scheduling requirements scale significantly.

5. **LEMUR vs SARM — different philosophies**: SARM (Kuaishou) uses an LLM to generate natural-language "semantic anchors" offline, then encodes them lightly — suited for non-stationary live-streaming content. Cotrain (ByteDance) trains a text Transformer end-to-end — suited for large-scale search and e-commerce. Both solve "multimodal-ranking decoupling," but from opposite angles: SARM improves the "understand then rank" pipeline; Cotrain eliminates the two-stage boundary entirely.

## Future Work (Team's Perspective)

**Performance:**
- Enable important items in user sequences to participate in VLM training, expanding coverage and reducing staleness
- Lower-invasiveness integration to avoid VLM becoming a compute bottleneck; efficient reuse of the multimodal component across experiments
- Scale VLM to large models (e.g., Seed 1.6 36B) with parallel training

**Representation:**
- Move beyond contrastive learning as the primary auxiliary loss; introduce richer supervision like Grounding
- Let VLM directly receive gradients from CTR/CVR business objectives end-to-end
- Design better mechanisms to manage embedding staleness as DLRM continues online learning

## References

- [LEMUR: Large scale End-to-end MUltimodal Recommendation](https://arxiv.org/abs/2511.10962) (arXiv 2511.10962)
- LONGER (long-sequence modeling, ByteDance internal work)
- MoCo / Memory Bank (visual SSL pioneers)
- Meta's recommendation system new paradigm
