---
title: 推荐系统
---

推荐系统的架构设计、模型训练、生成式推荐与线上服务知识体系。建议先读基础系统，再进入推荐大模型、生成式推荐和直播推荐。

## 学习路径

```text
级联推荐基础
    ↓
大推荐模型与长序列
    ↓
Semantic ID 与生成式推荐
    ↓
直播动态内容与推荐推理
```

## 推荐系统基础（Foundations）

- [[foundations/index|专题导航：召回、粗排、精排、多目标与探索]]
- [[foundations/industrial-recommender-pipeline|工业推荐系统全景]]
- [[foundations/multi-stage-objective-alignment|多阶段目标对齐]]
- [[foundations/multi-objective-debiasing|多目标推荐中的偏差]]

## 模型与架构（Models）

- [[models/index|专题导航：LRM、Scaling、长序列与 Co-design]]
- [[models/recommender-scaling-laws|推荐模型的 Scaling Law]]
- [[models/ultra-long-sequence-modeling|20K 用户行为如何进入在线模型]]
- [[models/kunlun-scaling-architecture|Kunlun 架构精讲]]
- [[models/unidot-explicit-interactions|UniDot 与 FM Highway]]

## 生成式推荐（Generative Recommendation）

- [[generative-recommendation/index|专题导航：从 Semantic ID 到推荐推理]]
- [[generative-recommendation/semantic-id-foundations|Semantic ID：生成式推荐的词表]]
- [[generative-recommendation/tiger-generative-retrieval|TIGER：生成式检索的起点]]
- [[generative-recommendation/onerec-unified-recommendation|OneRec：统一召回与排序]]
- [[generative-recommendation/reasoning-for-recommendation|从 OneRec-Think 到 OneReason]]

## 直播推荐（Live-streaming Recommendation）

- [[livestream/index|专题导航：动态内容、SID、前瞻预测与生态]]
- [[livestream/why-live-recommendation-is-different|直播推荐为什么是另一类问题]]
- [[livestream/dynamic-semantic-id|动态 Semantic ID]]
- [[livestream/foresight-content-prediction|前瞻内容预测]]

## 训练优化（Training）

模型训练中的关键技术，包括损失函数设计、数据采样等。

- [[in-batch-contrastive-loss|In-Batch Contrastive Loss：双塔模型训练的高效方案]]

## 线上服务（Serving）

推荐系统从离线模型到线上服务的部署与优化。

- [[serving-profile-guide|推荐系统线上 Profile 指南：从数据采样到向量召回]]

## 论文精读（Papers Reading）

学术论文的深度解读与工程应用思考。

- [[lemur-e2e-multimodal-rec|LEMUR：端到端多模态推荐系统的融合之道]]
- [[sarm-llm-livestream-ranking|SARM：LLM 赋能的直播排序系统]]
- [[ai-agent-ranking-optimization|Sortify：当 AI Agent 接管推荐系统的排序优化]]

## 推荐阅读顺序

第一次系统学习可以按下面顺序阅读：

1. [[foundations/industrial-recommender-pipeline|工业推荐系统全景]]
2. [[models/id-based-lrm-evolution|ID-Based 大推荐模型发展史]]
3. [[models/recommender-scaling-laws|推荐模型的 Scaling Law]]
4. [[generative-recommendation/semantic-id-foundations|Semantic ID]]
5. [[generative-recommendation/tiger-generative-retrieval|TIGER]]
6. [[generative-recommendation/onerec-unified-recommendation|OneRec]]
7. [[livestream/why-live-recommendation-is-different|直播推荐的特殊性]]
8. [[generative-recommendation/reasoning-for-recommendation|推荐推理]]
