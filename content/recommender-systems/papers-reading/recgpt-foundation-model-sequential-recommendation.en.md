---
title: "RecGPT: A Foundation Model for Sequential Recommendation"
date: 2026-03-25
tags:
  - recommender-systems
  - foundation-model
  - cross-domain-generalization
lang: en
chinese: recgpt-foundation-model-sequential-recommendation
---

> 🌐 [Read in Chinese](./recgpt-foundation-model-sequential-recommendation.md)

Paper reading notes: [A Foundation Model for Sequential Recommendation](https://arxiv.org/abs/2506.06270)

**Authors**: Yangqin Jiang, Xubin Ren, Lianghao Xia, Da Luo, Kangyi Lin, Chao Huang (The University of Hong Kong & Tencent)

**Code**: [https://github.com/HKUDS/RecGPT](https://github.com/HKUDS/RecGPT)

---

## Core Idea

### The Problem: Why Do Recommender Systems Need a Foundation Model?

Traditional recommender systems (SASRec, BERT4Rec, etc.) rely on **item ID embeddings** as their core representation—one independent vector per item. This creates three fundamental problems:

1. **Cold-start failure**: New items have no interaction history, so ID embeddings cannot learn meaningful representations
2. **No cross-domain transferability**: Embeddings learned on Amazon are completely useless for Yelp, since the ID spaces are disjoint
3. **Retraining required for every new domain**: Expensive and impractical

NLP and CV solved the cross-domain generalization problem long ago through foundation models (GPT, ViT). The core insight is: **unified tokenization + autoregressive modeling = cross-domain generalization**. Can recommender systems do the same?

### The Solution: RecGPT

RecGPT's core idea: **reformulate sequential recommendation as a next-token prediction problem**.

However, directly applying language model approaches doesn't work, because of three unique challenges:

| Challenge | Language Models | Recommender Systems |
|-----------|----------------|---------------------|
| Tokenization | Fixed vocabulary, BPE/SentencePiece | Heterogeneous item descriptions, different formats across domains |
| Attention | Tokens are treated equally | Tokens within an item need bidirectional interaction; items need causal relationships |
| Decoding | Limited vocabulary (~50K) | Enormous token combination space ($L^{d_{fsq}}$), but the number of valid items is far smaller |

RecGPT designs a dedicated solution for each challenge:
- **Finite Scalar Quantization (FSQ)** → Unified item tokenization
- **Hybrid bidirectional-causal attention** → Correctly modeling hierarchical dependencies
- **Catalog-aware Beam Search + Trie** → Efficient decoding

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RecGPT Architecture Overview                     │
├──────────────────┬──────────────────────┬───────────────────────────┤
│  (i) Unified Item │  (ii) Universal Rec  │  (iii) Efficient Token    │
│     Tokenization  │       Modeling        │        Decoding           │
│                  │                      │                           │
│  Item Text       │   Token Embed Table  │   Beam Search             │
│    ↓             │        ↓             │      ↓                    │
│  MPNet Encoder   │   Aux Embed (cont.)  │   Trie Prefix Constraint  │
│    ↓             │        ↓             │      ↓                    │
│  Continuous Emb  │   LNorm + Sum + Pos  │   Candidate Filtering     │
│    ↓             │        ↓             │      ↓                    │
│  FSQ Quantize    │   Transformer Layers │   Top-K Items             │
│    ↓             │   (Hybrid Attention) │                           │
│  Discrete Tokens │        ↓             │                           │
│                  │   Autoregressive Loss│                           │
└──────────────────┴──────────────────────┴───────────────────────────┘
```

---

## Method Details

### 2.1 Unified Item Tokenization

#### 2.1.1 Text Encoding

RecGPT uses **MPNet** as the text encoder, encoding an item's textual features (title, category, description, etc.) into continuous vectors. MPNet's advantage is its joint use of Masked Language Modeling (MLM) and Permuted Language Modeling (PLM).

MPNet's training objective:

$$\mathbb{E}_{z \in \mathcal{Z}_n} \sum_{t=c+1}^{n} \log P(x_{z_t} | x_{z_{<t}}, \Phi_{z_{>c}}; \theta)$$

where $\mathcal{Z}_n$ is the set of permutations of indices $(1, \cdots, n)$, $z_t$ is the $t$-th index in a permutation, and $\Phi_{z_{>c}}$ is the mask at positions $z_{>c}$.

After encoding, each item $i$ gets a $d_L$-dimensional vector:

$$e_i = \text{MPNet}(X_i), \quad e_i \in \mathbb{R}^{d_L}$$

**Why text instead of IDs?** Because text is "domain-agnostic"—whether it's an Amazon product title or a Yelp restaurant name, the text encoder can extract semantics. This is the foundation for cross-domain generalization.

#### 2.1.2 Finite Scalar Quantization (FSQ)

This is one of RecGPT's most critical innovations. The goal is to **discretize continuous text embeddings into token sequences**, enabling autoregressive modeling.

**Steps**:

1. **Split**: Divide the $d_L$-dimensional $e_i$ into $K$ sub-vectors $e_i^k \in \mathbb{R}^{d_L/K}$
2. **Dimensionality reduction**: Linear transform $T_{in}(e_i^k) = W_{in} e_i^k + b$, from $d_L/K$ down to $d_{fsq}$
3. **Normalization**: Sigmoid function $\sigma(\cdot)$ maps values to $(0, 1)$
4. **Discretization**: Round to integers in $\{0, 1, \ldots, L-1\}$

$$\text{FSQ}(e_i^k) = R[(L-1)\sigma(T_{in}(e_i^k))]$$

where $R[\cdot]$ is the rounding operation and $L$ is the number of quantization levels. Each sub-vector is quantized to a $d_{fsq}$-dimensional integer vector, with a codebook size of $|C| = L^{d_{fsq}}$.

**What about gradients?** Rounding is non-differentiable, so they use the **Straight-Through Estimator (STE)**:

$$\text{FSQ}(e_i^k) = (L-1)\sigma(T_{in}(e_i^k)) + \text{sg}[R[(L-1)\sigma(T_{in}(e_i^k))] - (L-1)\sigma(T_{in}(e_i^k))]$$

$\text{sg}[\cdot]$ is the stop gradient operation—forward pass uses discrete values, backward pass lets gradients flow through.

**Why FSQ over VQ-VAE?** FSQ elegantly solves VQ-VAE's **codebook collapse** problem (where most codes go unused). FSQ doesn't maintain an explicit codebook; each dimension is quantized independently, naturally avoiding collapse.

**Specific configuration**: $d_{fsq} = 5$, quantization levels $L = [8, 8, 8, 6, 5]$, codebook size $= 8 \times 8 \times 8 \times 6 \times 5 = 15360$. Each item is represented with $K = 4$ tokens.

#### 2.1.3 Quantization Optimization

Post-quantization, we need to be able to reconstruct the original embeddings. A multi-layer Transformer decoder is trained for reconstruction using **L1 loss**:

$$\mathcal{L}_{fsq} = \sum_{i=0}^{N-1} \| e_i - \text{Decoder}([T_{out}(\hat{e}_i^0), \cdots, T_{out}(\hat{e}_i^{K-1})]) \|_1$$

where $\hat{e}_i^k$ is the quantized representation and $T_{out}$ is the dimension expansion transform (from $d_{fsq}$ back to $d_L/K$). L1 is preferred over L2 because L1 is more robust to outliers, helping preserve discriminative semantic features.

### 2.2 Universal Recommendation Modeling

#### 2.2.1 Hybrid Bidirectional-Causal Attention

This is RecGPT's second core innovation. The problem: when an item is represented by multiple tokens, standard causal attention (GPT-style) restricts information flow between tokens within the same item.

Solution: **Two-level attention mechanism**
- **Intra-item**: Bidirectional attention—tokens within the same item can freely exchange information
- **Inter-item**: Causal attention—can only see previous items, maintaining temporal causality

```
Item 1 tokens: [t1, t2, t3, t4]    Item 2 tokens: [t5, t6, t7, t8]
              ←→ bidir ←→                         ←→ bidir ←→
                    |                                  |
                    └────── causal (look right only) ──────→
```

**Why is this needed?** In language models, each token is an independent "word," but in RecGPT, 4 tokens collectively represent one item. If token $t_2$ can't see $t_3$ and $t_4$ (due to the causal mask), it can't form a complete item representation. Bidirectional attention solves this.

#### 2.2.2 Auxiliary Semantic Features

Quantization inevitably causes information loss. RecGPT mitigates this through **dual-stream representation**:

- **Token embeddings** $E_{wte} \in \mathbb{R}^{T \times d_{ar}}$: Learned embeddings for discrete tokens
- **Auxiliary embeddings** $E_{aux} \in \mathbb{R}^{T \times d_{ar}}$: Linear projection of original continuous semantic features

The final input fuses both with positional encoding:

$$X = \text{LNorm}(E_{aux}) + \text{LNorm}(E_{wte}) + E_{wpe}$$

where $E_{wpe} \in \mathbb{R}^{T \times d_{ar}}$ is the positional embedding. LayerNorm normalizes each stream independently for numerical stability.

### 2.3 Training Objective

Standard autoregressive next-token prediction loss:

$$\mathcal{L}_{ar} = -\sum_{t=0}^{T-1} \log P\left(Y_t \mid X_{< \lfloor \frac{t}{K} \rfloor \times K}\right)$$

A key detail: $\lfloor \frac{t}{K} \rfloor \times K$ ensures that when predicting the $t$-th token, the model can only see all tokens from previous **complete items** (not all preceding tokens). Combined with bidirectional attention, the model can **predict all $K$ tokens of the next item simultaneously** during training.

### 2.4 Efficient Item Token Decoding

#### 2.4.1 Beam Search

At inference time, RecGPT **predicts $K$ tokens in parallel** in a single forward pass (thanks to the bidirectional attention design), then uses beam search over the joint probability distribution of these $K$ tokens to find the top-n most likely token sequences.

#### 2.4.2 Trie-based Catalog-Aware Constraint

Core insight: Theoretically, the token combination space has $L^{d_{fsq}} = 15360^4$ possibilities, but the actual catalog only contains hundreds of thousands to millions of items.

Approach: Build a **Trie (prefix tree)** from the token sequences of all items in the catalog. As beam search generates each token, it queries the Trie and only retains branches that can reach valid items.

Benefits:
1. No computation wasted on invalid token combinations
2. Guaranteed that recommended results are real items in the catalog

---

## Experimental Setup

### Datasets

| Dataset | #Users | #Items | #Interactions | Avg Seq Length |
|---------|--------|--------|---------------|----------------|
| **Pre-training (11 Amazon subcategories)** | 12,472,073 | 15,491,643 | 131,657,450 | 10.56 |
| - Books | 1,091,587 | 2,978,216 | 13,859,969 | 12.69 |
| - Clothing | 3,088,673 | 4,875,707 | 30,245,204 | 9.79 |
| - Electronics | 1,692,840 | 1,128,480 | 16,248,100 | 9.59 |
| - Kitchen | 3,096,330 | 2,742,128 | 30,758,013 | 9.93 |
| **Validation (3 Amazon subcategories)** | 184,674 | 377,186 | 1,615,405 | 8.75 |
| **Test - Amazon** | | | | |
| Baby | 184,851 | 123,537 | 1,551,060 | 8.39 |
| Games | 117,742 | 83,137 | 1,030,529 | 8.75 |
| Office | 333,744 | 363,786 | 2,735,472 | 8.19 |
| **Test - Cross-platform** | | | | |
| Yelp | 287,116 | 148,523 | 4,392,168 | 15.29 |
| Washington | 625,428 | 120,080 | 12,382,314 | 19.79 |
| Steam | 334,594 | 15,066 | 4,214,640 | 12.59 |

Pre-training data scale: **130 million interactions**, covering 11 Amazon product categories.

### Model Configuration

- Max sequence length $T = 1024$, hidden dimension $d_{ar} = 768$
- Positional embedding dimensions: $\mathbb{R}^{1025 \times 768}$
- FSQ: $d_{fsq} = 5$, $L = [8,8,8,6,5]$, vocabulary size 15,360
- Each item represented with $K = 4$ tokens
- Decoder: GPT-2 architecture, 3-layer Transformer
- Token embedding table: $\mathbb{R}^{15360 \times 768}$
- Training hardware: 4 × A100 40G (also verified feasible on a single RTX 3090 24G)

### Baselines

9 traditional methods + 6 pre-training methods:

- **RNN**: GRU4Rec, GRU4RecF
- **CNN**: Caser
- **Transformer**: BERT4Rec, FDSA
- **Contrastive Learning**: CL4SRec, DuoRec, ICLRec, MAERec
- **Pre-training**: S3-Rec, UniSRec, VQ-Rec, TIGER, RecFormer, IDGenRec

---

## Experimental Results

### Zero-shot Cross-domain Recommendation (Table 1)

RecGPT uses **no target domain training data** (zero-shot), compared against other methods using **10% target domain data** (few-shot).

**Amazon same-platform cross-domain** (selected key metrics):

| Dataset | Metric | Best Baseline | RecGPT (zero-shot) | Improvement |
|---------|--------|---------------|---------------------|-------------|
| Baby | Hit@1 | 0.0025 (multiple methods) | **0.0273** | ~10× |
| Baby | NDCG@5 | 0.0063 (DuoRec) | **0.0279** | ~4.4× |
| Games | Hit@1 | 0.0045 (CL4SRec) | **0.0364** | ~8× |
| Games | NDCG@5 | 0.0103 (CL4SRec) | **0.0371** | ~3.6× |
| Office | Hit@1 | 0.0022 (DuoRec) | **0.0280** | ~12.7× |
| Office | NDCG@5 | 0.0041 (FDSA) | **0.0290** | ~7× |

**Cross-platform** (selected key metrics):

| Dataset | Metric | Best Baseline | RecGPT (zero-shot) | Improvement |
|---------|--------|---------------|---------------------|-------------|
| Yelp | Hit@1 | 0.0029 (MAERec) | **0.0161** | ~5.6× |
| Yelp | NDCG@5 | 0.0074 (MAERec) | **0.0163** | ~2.2× |
| Washington | Hit@1 | 0.0041 (MAERec) | **0.0122** | ~3× |
| Steam | Hit@1 | 0.1022 (FDSA) | **0.1237** | ~1.2× |
| Steam | NDCG@5 | 0.1232 (FDSA) | **0.1245** | ~1.01× |

Key findings:
- Massive advantages on Amazon sub-domains (>10× Hit@1 improvement), since pre-training data is also from Amazon
- Clear but smaller advantages cross-platform (Yelp, Washington), indicating that platform differences are real
- On the Steam dataset, FDSA's few-shot is already strong (0.1022 Hit@1), and RecGPT still surpasses it (0.1237), but the margin narrows

### Cold-start Recommendation (Table 2)

Each user retains only 1-3 interaction records, predicting the next interaction.

| Dataset | Metric | Best Baseline | RecGPT | 
|---------|--------|---------------|--------|
| Baby | Hit@1 | 0.0099 (DuoRec) | **0.0165** |
| Baby | NDCG@5 | 0.0153 (DuoRec) | **0.0169** |
| Office | Hit@1 | 0.0096 (DuoRec) | **0.0188** |
| Office | NDCG@5 | 0.0154 (DuoRec) | **0.0197** |
| Yelp | Hit@1 | 0.0063 (DuoRec) | **0.0126** |
| Yelp | NDCG@5 | 0.0141 (DuoRec) | **0.0128** |

Note: On Yelp's Hit@3/5, RecGPT isn't always the best (FDSA, DuoRec, etc. reach 0.0219-0.0221 on Hit@5), indicating that under extreme cold-start conditions, while RecGPT excels at Hit@1, its advantage diminishes under more lenient metrics.

### Industrial Deployment Validation

Validated on a news recommendation platform with millions of daily active users:
- 163,385 users, 455,372 content items, 999,140 interaction records
- RecGPT significantly outperforms all baselines (including BERT4Rec, FDSA, CL4SRec, DuoRec, MAERec, S3-Rec) on both Hit@5 and NDCG@5

### Comparison with Pre-training Recommendation Methods (Figures 6 & 7)

RecGPT surpasses S3-Rec, UniSRec, VQ-Rec, TIGER, IDGenRec, and RecFormer on Hit@5 and NDCG@5 across Baby, Office, and Yelp.

**Key controlled experiments**:
- **RecGPT-10%** (trained with only 10% of data, with reduced parameters) still outperforms the original VQ-Rec
- **VQ-Rec (Re-trained)** (VQ-Rec retrained with RecGPT's full dataset) actually shows degraded performance

This proves RecGPT's advantage comes not just from data scale, but from **architectural design** (decoder-only + autoregressive objective).

---

## Ablation Analysis (Table 3)

| Variant | Baby Hit@5 | Baby NDCG@5 | Office Hit@5 | Office NDCG@5 | Yelp Hit@5 | Yelp NDCG@5 |
|---------|-----------|-------------|-------------|--------------|-----------|-------------|
| w/o FSQ | 0.0178 | 0.0177 | 0.0167 | 0.0166 | 0.0139 | 0.0138 |
| w/o Bidir | 0.0279 | 0.0275 | 0.0288 | 0.0283 | 0.0162 | 0.0158 |
| w/o Aux | 0.0191 | 0.0189 | 0.0205 | 0.0200 | 0.0075 | 0.0065 |
| w/o Pref | 0.0282 | 0.0274 | 0.0281 | 0.0280 | 0.0162 | 0.0161 |
| **RecGPT** | **0.0283** | **0.0279** | **0.0299** | **0.0290** | **0.0166** | **0.0163** |

**Component impact analysis**:

1. **FSQ is the most critical**: Removing FSQ (using random tokens) causes the largest drop. Baby Hit@5 drops from 0.0283 to 0.0178 (-37%), Office from 0.0299 to 0.0167 (-44%). Semantics-preserving tokenization is the cornerstone of cross-domain generalization.

2. **Auxiliary semantic features matter significantly**: Removing Aux drops Yelp NDCG@5 from 0.0163 to 0.0065 (-60%), showing that quantization information loss is especially severe in cross-platform scenarios.

3. **Bidirectional attention helps but isn't decisive**: Removing Bidir barely affects Baby (0.0283→0.0279), but noticeably impacts Office (0.0299→0.0288).

4. **Trie prefix constraint has minimal impact**: w/o Pref shows very small drops, indicating it primarily improves efficiency rather than quality.

### Scaling Law (Figures 4 & 5)

Trained with 5%, 10%, 25%, 50%, and 100% of training data:

- **Key finding**: There's a disproportionate performance jump between 10% and 25%, hinting at an "emergent capability threshold"
- Evaluation loss decreases following a **power-law** with training tokens (consistent with LLM scaling laws)
- Power-law fitting on the 5%-50% data points can accurately predict 100% performance

Practical implication: **Scaling training data is more efficient than scaling model size**—important for industrial deployment since it doesn't increase inference cost.

---

## Points Worth Reflecting On

### 1. FSQ vs VQ-VAE: Is Simple Better?

RecGPT choosing FSQ over the more common VQ-VAE/RQ is an interesting decision. FSQ essentially "quantizes each dimension independently to a few integers"—looks crude but elegantly avoids codebook collapse. This reminds me of a broader trend: **in large-scale systems, simple, stable methods often outperform clever but fragile ones**. VQ-Rec used VQ but actually degraded with more data, likely due to codebook management issues.

### 2. The Real Ceiling of Cross-platform Generalization

While RecGPT's generalization across Amazon sub-domains is impressive (10× improvement), the advantage shrinks noticeably cross-platform (Amazon→Yelp/Steam). This suggests **text semantics alone cannot fully capture differences in recommendation behavior**—people's browsing patterns on e-commerce are fundamentally different from their selection patterns on gaming platforms. Text is just one aspect of an item; behavioral patterns (browsing vs. purchasing vs. rating) may need additional modeling.

### 3. Are 4 Tokens Enough?

Each item is represented with $K=4$ tokens, with a codebook size of 15,360. Theoretically, this can distinguish $15360^4 \approx 5.6 \times 10^{16}$ items, far exceeding practical needs. But the question is: **can 4 tokens sufficiently encode an item's semantics?** The paper doesn't include an ablation on $K$. Intuitively, too small a $K$ loses information, while too large a $K$ makes sequences too long and hurts efficiency. This trade-off deserves deeper investigation.

### 4. Autoregressive vs Bidirectional: The Right Paradigm for Recommendation?

RecGPT uses a decoder-only architecture with an autoregressive objective, mirroring GPT. But BERT4Rec uses an encoder with MLM (similar to BERT) and previously demonstrated that bidirectional encoding works better for recommendation. RecGPT's hybrid attention effectively "smuggles" bidirectional information (within items) into an autoregressive framework. A natural question: **would a fully bidirectional encoder architecture + FSQ tokenization perform even better?** The paper doesn't explore this direction.

### 5. Practical Considerations for Industrial Deployment

The paper mentions RecGPT is deployed on Tencent's news recommendation platform, but provides few details. Key practical questions:
- **Trie update frequency**: When new items go live, does the Trie need rebuilding or incremental updates?
- **Inference latency**: What's the actual time cost of beam search + Trie lookup?
- **Fusion with traditional signals**: The paper acknowledges in its Limitations that RecGPT cannot yet fully replace core user profile signals. In production systems, RecGPT is more likely to serve as a **recall/supplementary signal** rather than the sole ranking model.

---

## Summary

RecGPT is a well-designed system where three core components (FSQ tokenization, hybrid attention, Trie decoding) each solve a clear problem. The most impressive aspect is the **massive zero-shot advantage on Amazon sub-domains**—demonstrating that the foundation model approach for recommender systems is viable.

That said, limitations remain: cross-platform generalization is still limited, cold-start advantages don't always hold under lenient metrics, and industrial deployment details are insufficient. As the "first" general-purpose sequential recommendation foundation model, RecGPT is more of a directional proof of concept than an ultimate solution.

---

**References**:
- Paper: [arXiv:2506.06270](https://arxiv.org/abs/2506.06270)
- Code: [https://github.com/HKUDS/RecGPT](https://github.com/HKUDS/RecGPT)
- Original FSQ paper: [Finite Scalar Quantization: VQ-VAE Made Simple (arXiv:2309.15505)](https://arxiv.org/abs/2309.15505)
- MPNet: [MPNet: Masked and Permuted Pre-training for Language Understanding (NeurIPS 2020)](https://arxiv.org/abs/2004.09297)
- VQ-Rec: [Learning Vector-Quantized Item Representation for Transferable Sequential Recommenders (WWW 2023)](https://arxiv.org/abs/2210.12316)
- TIGER: [Recommender Systems with Generative Retrieval (NeurIPS 2023)](https://arxiv.org/abs/2305.05065)
