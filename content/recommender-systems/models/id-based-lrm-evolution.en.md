---
title: "The Evolution of ID-based Large Recommendation Models: From Collaborative Filtering to Trillion Parameters"
date: 2026-03-01
tags:
  - recommender systems
  - ID embedding
  - large recommendation models
  - survey
lang: en
chinese: recommender-systems/models/id-based-lrm-evolution
---

> 🌐 [中文版](./id-based-lrm-evolution.md)

## 2.1 Early Recommender Systems and Collaborative Filtering (1990s–2009)

The origins of recommender systems trace back to collaborative filtering (CF) in the 1990s. The GroupLens project [Resnick et al., 1994] pioneered the idea of user-rating-based CF, predicting preferences for unseen items by analyzing behavioral similarity between users. Early CF methods split into two camps: User-based CF and Item-based CF [Sarwar et al., 2001], both relying on user-item interaction matrices to discover latent preference patterns.

Matrix Factorization (MF) marked the first major milestone in ID-based recommendation modeling. The 2006 Netflix Prize dramatically accelerated progress. Simon Funk publicly shared FunkSVD, decomposing the user-item rating matrix into the product of two low-dimensional matrices [Funk, 2006]. SVD++ [Koren, 2008] extended this by incorporating implicit feedback, while Probabilistic Matrix Factorization (PMF) [Salakhutdinov & Mnih, 2008] provided a Bayesian statistical foundation.

This era established a defining paradigm: **ID embedding as the core modeling unit** — learning low-dimensional dense vector representations for user IDs and item IDs to capture collaborative interaction signals. This paradigm dominated recommender systems research for nearly 15 years.

Factorization Machines (FM) [Rendle, 2010] generalized matrix factorization to model second-order interactions between arbitrary features while naturally handling high-dimensional sparse inputs. FM and its variant FFM [Juan et al., 2016] became foundational industrial CTR models by combining ID embedding with feature interaction.

## 2.2 Deep Learning Recommendation Models (2016–2019)

2016 was the landmark year deep learning entered recommender systems. YouTube's deep neural network recommendation system [Covington et al., 2016] pioneered the **Embedding + MLP** paradigm at industrial scale, proving the effectiveness of ID embeddings in large-scale systems.

The same year, Google's Wide & Deep model [Cheng et al., 2016], deployed on Google Play, combined a wide linear model with a deep neural network to balance memorization and generalization. It became a classic industrial architecture.

Building on this, DeepFM [Guo et al., 2017] automatically combined FM components with deep networks, eliminating the need for manual feature crosses. DCN [Wang et al., 2017] introduced a cross network to automatically learn explicit feature interactions.

In 2018, Alibaba's DIN (Deep Interest Network) [Zhou et al., 2018] introduced attention mechanisms that adaptively weight a user's historical behaviors based on the candidate item — deployed in Alibaba's display advertising system. DIEN [Zhou et al., 2019] further modeled the dynamic evolution of user interests using GRU.

In 2019, Meta's DLRM [Naumov et al., 2019] systematically unified recommendation model design and introduced a hybrid parallelization scheme (model parallelism for embedding tables, data parallelism for fully-connected layers), becoming a key industrial benchmark.

## 2.3 Sequential Recommendation and Transformers (2018–2021)

Following Transformer's [Vaswani et al., 2017] success in NLP, researchers quickly applied it to sequential recommendation.

SASRec [Kang & McAuley, 2018] was first to apply a unidirectional Transformer decoder to sequential recommendation, replacing RNNs with self-attention — over an order of magnitude faster than RNN and CNN approaches.

BERT4Rec [Sun et al., 2019] brought bidirectional self-attention and a Cloze-style training objective, transferring BERT's masked language modeling paradigm to sequential recommendation.

A common thread: **item ID embeddings remain the fundamental modeling unit**. The Transformer architecture primarily models temporal dependencies and attention interactions across sequences of ID embeddings.

## 2.4 The Rise of Large Recommendation Models (2022–Present)

Inspired by the success of large language models, the recommendation community has seen a trend toward Large Recommendation Models (LRMs), exploring scaling laws in recommender systems.

- **HSTU** [Zhai et al., 2024]: Meta's work showing the possibility of scaling recommendation models to trillion parameters
- **Wukong** [Zhang et al., 2024]: Google's exploration of scaling behavior in large-scale recommendation
- **LiRank** [Varshney et al., 2024]: LinkedIn's application of large-scale Transformers to industrial user modeling
- **PinnerFormer** [Pancha et al., 2022]: Pinterest's Transformer-based sequential recommendation

In these systems, item ID embeddings remain the primary modeling unit, with most of the model's representational capacity allocated to embedding tables. While this ID-centric paradigm excels at capturing historical interaction patterns, it is fundamentally biased toward **memorization** of observed behavior.

For long-lived items (e.g., e-commerce products), sufficient interaction signals accumulate over time — ID embeddings can learn rich representations. However, **in live-streaming scenarios, room identifiers are typically ephemeral and short-lived**, invalidating the assumption of stable ID interaction accumulation. This is the core bottleneck of ID-based recommendation models in live-streaming.

## 2.5 Beyond Pure ID: Semantic IDs and Multimodal Representations

To overcome the cold-start and generalization limitations of pure ID modeling, researchers have explored alternative semantic abstraction mechanisms.

**Semantic ID direction**:
- YouTube's Semantic IDs (SIDs) [Singh et al., 2023]: Quantize item content features into compact discrete token sequences, enabling generalization from intrinsic item semantics
- TIGER [Rajput et al., 2023]: Uses RQ-VAE to quantize item embeddings into semantic IDs, decoded autoregressively by a Transformer

**Multimodal direction**:
- "Where to Go Next" [Yuan et al., 2023]: Systematically revisits IDRec vs. MoRec (modality-based models), finding that with a sufficiently strong pretrained modality encoder, MoRec can match or surpass IDRec in generalization, especially in cold-start scenarios

These works collectively point toward a trend: **combining the memorization capacity of ID with the generalization power of semantic/multimodal representations** to build more robust recommender systems.

---

## References

- [Resnick et al., 1994] [GroupLens: An open architecture for collaborative filtering of netnews.](https://dl.acm.org/doi/10.1145/192844.192905) CSCW.
- [Sarwar et al., 2001] [Item-based collaborative filtering recommendation algorithms.](https://dl.acm.org/doi/10.1145/371920.372071) WWW.
- [Funk, 2006] [Netflix Update: Try This at Home.](https://sifter.org/~simon/journal/20061211.html) Blog post.
- [Koren, 2008] [Factorization meets the neighborhood: a multifaceted collaborative filtering model.](https://dl.acm.org/doi/10.1145/1401890.1401944) KDD.
- [Salakhutdinov & Mnih, 2008] [Probabilistic matrix factorization.](https://proceedings.neurips.cc/paper/2007/hash/d7322ed717dedf1eb4e6e52a37ea7bcd-Abstract.html) NeurIPS.
- [Rendle, 2010] [Factorization machines.](https://ieeexplore.ieee.org/document/5694074) ICDM.
- [Juan et al., 2016] [Field-aware factorization machines for CTR prediction.](https://dl.acm.org/doi/10.1145/2959100.2959134) RecSys.
- [Covington et al., 2016] [Deep neural networks for YouTube recommendations.](https://dl.acm.org/doi/10.1145/2959100.2959190) RecSys.
- [Cheng et al., 2016] [Wide & deep learning for recommender systems.](https://arxiv.org/abs/1606.07792) DLRS@RecSys.
- [Guo et al., 2017] [DeepFM: A factorization-machine based neural network for CTR prediction.](https://arxiv.org/abs/1703.04247) IJCAI.
- [Wang et al., 2017] [Deep & cross network for ad click predictions.](https://arxiv.org/abs/1708.05123) ADKDD.
- [Zhou et al., 2018] [Deep interest network for click-through rate prediction.](https://arxiv.org/abs/1706.06978) KDD.
- [Zhou et al., 2019] [Deep interest evolution network for click-through rate prediction.](https://arxiv.org/abs/1809.03672) AAAI.
- [Naumov et al., 2019] [Deep learning recommendation model for personalization and recommendation systems.](https://arxiv.org/abs/1906.00091) arXiv.
- [Vaswani et al., 2017] [Attention is all you need.](https://arxiv.org/abs/1706.03762) NeurIPS.
- [Kang & McAuley, 2018] [Self-attentive sequential recommendation.](https://arxiv.org/abs/1808.09781) ICDM.
- [Sun et al., 2019] [BERT4Rec: Sequential recommendation with bidirectional encoder representations from transformer.](https://arxiv.org/abs/1904.06690) CIKM.
- [Zhai et al., 2024] [Actions speak louder than words: Trillion-parameter sequential transducers for generative recommendations.](https://arxiv.org/abs/2402.17152) ICML.
- [Zhang et al., 2024] [Wukong: Towards a scaling law for large-scale recommendation.](https://arxiv.org/abs/2403.02545) ICML.
- [Singh et al., 2023] [Better generalization with semantic IDs: A case study in ranking for recommendations.](https://arxiv.org/abs/2306.08121) arXiv.
- [Rajput et al., 2023] [Recommender systems with generative retrieval.](https://arxiv.org/abs/2305.05065) NeurIPS.
- [Yuan et al., 2023] [Where to go next for recommender systems? ID- vs. modality-based recommender models revisited.](https://arxiv.org/abs/2208.09912) SIGIR.
