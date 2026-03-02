---
title: "ID-based 大推荐模型发展史：从协同过滤到万亿参数"
date: 2026-03-01
tags:
  - 推荐系统
  - ID Embedding
  - 大推荐模型
  - 综述
lang: zh
english: recommender-systems/models/id-based-lrm-evolution.en
---

> 🌐 [Read in English](./id-based-lrm-evolution.en.md)

## 2.1 早期推荐系统与协同过滤（1990s–2009）

推荐系统的起源可以追溯到1990年代的协同过滤（Collaborative Filtering, CF）技术。GroupLens项目 [Resnick et al., 1994] 率先提出了基于用户评分的协同过滤思想，通过分析用户之间的行为相似性来预测其对未见物品的偏好。早期的协同过滤方法主要分为两类：基于用户的（User-based CF）和基于物品的（Item-based CF）[Sarwar et al., 2001]。这些方法的核心在于利用用户ID和物品ID之间的交互矩阵来发现隐含的偏好模式。

矩阵分解（Matrix Factorization, MF）的引入标志着ID-based推荐建模的第一个重要里程碑。2006年Netflix Prize竞赛的发起极大地推动了这一领域的发展。Simon Funk公开了FunkSVD方法，将用户-物品评分矩阵分解为两个低维矩阵的乘积 [Funk, 2006]。随后，SVD++ [Koren, 2008] 引入了隐式反馈信息，概率矩阵分解（PMF）[Salakhutdinov & Mnih, 2008] 则为这一范式提供了贝叶斯统计基础。

这一时期确立了 **ID embedding 作为推荐系统核心建模单元的范式**——通过学习用户ID和物品ID的低维稠密向量表示来捕获协同交互信号，这一思路主导了推荐系统领域近15年的发展。

Rendle [2010] 提出的因子分解机（Factorization Machines, FM）进一步泛化了矩阵分解的思路，能够对任意特征之间的二阶交互进行建模，同时天然地处理高维稀疏特征。FM及其变体FFM [Juan et al., 2016] 将ID embedding与特征交互结合，成为工业界CTR预估的重要基础模型。

## 2.2 深度学习推荐模型（2016–2019）

2016年是深度学习进入推荐系统的标志性年份。YouTube的深度神经网络推荐系统 [Covington et al., 2016] 开创了"Embedding + MLP"的推荐建模范式，证明了ID embedding在大规模推荐系统中的有效性。

同年，Google提出的 Wide & Deep 模型 [Cheng et al., 2016] 通过联合训练宽线性模型和深度神经网络，结合记忆化（memorization）和泛化（generalization）的优势，成为工业推荐系统的经典架构。

在此基础上，DeepFM [Guo et al., 2017] 将FM组件与深度网络自动结合；DCN [Wang et al., 2017] 引入交叉网络来自动学习显式特征交互。

2018年，阿里巴巴的DIN（Deep Interest Network）[Zhou et al., 2018] 引入注意力机制，根据候选广告的不同对用户历史行为赋予不同权重，成功部署在展示广告系统中。随后的DIEN [Zhou et al., 2019] 进一步引入GRU建模用户兴趣的动态演化。

2019年，Meta的DLRM [Naumov et al., 2019] 系统性地统一了推荐模型的设计范式，并提出了混合并行化方案（embedding表用模型并行，全连接层用数据并行），成为工业级推荐系统的重要基准。

## 2.3 序列推荐与Transformer（2018–2021）

随着Transformer [Vaswani et al., 2017] 在NLP领域取得成功，研究者迅速将其引入序列推荐。

SASRec [Kang & McAuley, 2018] 首先将单向Transformer解码器应用于序列推荐，使用自注意力机制取代RNN，推理速度比RNN和CNN方法快一个数量级以上。

BERT4Rec [Sun et al., 2019] 引入双向自注意力机制和完形填空训练目标，将BERT的掩码语言模型范式迁移到序列推荐中，在多个公开数据集上取得显著提升。

这些方法的共同点：**仍然以物品ID embedding作为基本建模单元**，Transformer主要用于建模ID embedding序列之间的时序依赖和注意力交互。

## 2.4 大规模推荐模型（LRM）的兴起（2022–至今）

受大语言模型成功的启发，推荐系统领域出现了"大推荐模型"（Large Recommendation Models, LRM）的趋势，试图探索推荐系统中的缩放定律（scaling laws）。

- **HSTU** [Zhai et al., 2024]：Meta提出，展示了将推荐模型扩展到万亿参数级别的可能性
- **Wukong** [Zhang et al., 2024]：Google提出，探索大规模推荐模型的缩放行为
- **LiRank** [Varshney et al., 2024]：LinkedIn，大规模Transformer在工业用户建模中的应用
- **PinnerFormer** [Pancha et al., 2022]：Pinterest，序列推荐的Transformer应用

在这些系统中，物品ID embedding仍然是主要的建模单元，模型的大部分表示能力被分配给ID embedding表。虽然这种以ID为中心的建模范式在捕捉历史交互模式方面表现优异，但其本质上偏向于对已有行为模式的**记忆（memorization）**。

对于长寿命的物品（如电商商品），可以积累充足的交互信号，ID embedding能学到丰富的表示。然而，**在实时直播场景中，直播间标识符通常是短暂和临时的（ephemeral）**，稳定的ID交互积累假设不再成立，这构成了ID-based推荐模型在直播推荐中的核心瓶颈。

## 2.5 超越纯ID：语义ID与多模态表示

为了克服纯ID建模的冷启动和泛化不足问题，研究者开始探索替代性的语义抽象机制。

**语义ID方向**：
- YouTube的语义ID（SIDs）[Singh et al., 2023]：将物品内容特征量化为紧凑的离散token序列，使推荐模型能从物品内在语义属性中泛化
- TIGER [Rajput et al., 2023]：使用RQ-VAE将物品embedding量化为语义ID，由Transformer自回归解码

**多模态方向**：
- "Where to Go Next" [Yuan et al., 2023]：系统性对比IDRec与MoRec（模态-based模型），发现预训练模态编码器足够强大时，MoRec在冷启动场景下优势明显

这些工作共同指向一个趋势：**结合ID的记忆能力与语义/多模态表示的泛化能力**，构建更加鲁棒的推荐系统。

---

## 主要参考文献

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
