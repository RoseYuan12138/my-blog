---
title: "生成式推荐（GR）迭代脉络与经典论文：从 TIGER 到统一用户理解"
date: 2026-09-11
tags:
  - 推荐系统
  - 生成式推荐
  - 论文综述
  - Semantic ID
lang: zh
---

生成式推荐的论文越来越多，但如果只记模型名字，很容易把 SID、序列排序、端到端生成和推理增强混成同一件事。更有效的读法是追踪问题：**每一代工作试图消除哪种重复计算、补上哪种目标错位，又保留了哪些必要的决策能力？**

本文整理截至 2026 年 9 月 11 日的公开论文，以 A–H 八条路线串起演进逻辑。各路线相互交叉；文中实验数字均为对应论文在特定数据、基线和流量范围内的报告，不宜跨论文直接比较。架构走向部分是阅读后的判断。

## 10 分钟建立全局认知

### 什么是 Generative Recommendation（GR）

传统推荐是"召回→粗排→精排→重排"级联：先从海量 item 找候选，再逐层打分。**GR 的核心变化：把"选物品"重述成序列建模/生成问题**——狭义的生成式检索直接生成 item 表示或 Semantic ID，进一步可以生成候选集合乃至有序 slate；广义的生成式推荐还包括 HSTU、GenRank 这类以序列转导架构完成排序的工作。

**最重要的直觉**：GR ≠「推荐里塞了个 LLM」。本质是把推荐从"独立 item scoring"推向 **sequence generation / policy learning / shared foundation model**。

### 为什么会走到 GR

1. 多阶段系统越来越碎：召回/排序各训各的、各服务各的，用户历史被重复编码，目标还不一致。
2. Transformer 成为各阶段共同 backbone 后，"为什么每层都要重算一遍用户表示？"变成现实问题。
3. **Semantic ID** 把百万/十亿 item 的检索，变成小词表上的层级 token 生成 → 大规模生成式召回有了可计算路径。
4. 工业目标越来越多（点击/时长/点赞/转化/GMV/留存/多样性…）→ GR 逐渐向 **可控 policy** 演进。

### 一张表看懂演进主线

| 阶段                      | 时间      | 代表工作                               | 核心问题                                              |
| ------------------------- | --------- | -------------------------------------- | ----------------------------------------------------- |
| **前传·序列推荐**         | 2016–2019 | GRU4Rec → SASRec → BERT4Rec            | 把用户历史当序列建模，预测 next item（GR 的地基）     |
| **A·生成式检索诞生**      | 2022–2025 | DSI / P5 → **TIGER** → PinRec          | 能不能"生成" item 的地址(SID)来替代向量近邻召回？     |
| **A'·生成式排序/Scaling** | 2024–2025 | **HSTU** → GenRank                     | 生成式架构 + Scaling Law 能不能直接提升排序？         |
| **B·挑战整个级联**        | 2025–2026 | OneRec / Sona                          | 能不能一个模型生成最终推荐，替掉多阶段？              |
| **C·发现"生成≠排序"**     | 2026      | Gryphon / UniPinRec / UniR² / UniSGR   | SID likelihood 不等于 item 价值，ranking 以新形式回归 |
| **D·多目标/可控 policy**  | 2026      | Multi-Decoder OneRec / OneRanker / OGR | 多业务目标、slate 效用、reward 怎么统一？             |
| **E·偏好对齐/RL**         | 2025–2026 | OneRec(IPA/DPO) / OGR                  | 从"像历史"对齐到"最大化真实 utility"                  |
| **F·Reasoning**           | 2025–2026 | OneRec-Think / TGR                     | 把语义/推理能力引入推荐，同时控住线上成本             |
| **G·表示/Tokenizer**      | 2022→2026 | RQ-VAE → TIGER → DIGER                 | item 的"语言"(SID)本身要不要为推荐目标联合学习？      |
| **H·多域/Foundation**     | 2026      | MBGR / Foundation backbone             | 跨场景共享 user intelligence，同时保留业务专门化      |

**一句话串起来**：先证明能生成（A）→ 干脆替掉整条链路（B）→ 发现生成不等于排序、把排序请回来（C）→ 从单目标走向可控 policy（D/E）→ 引入 reasoning、走向 foundation（F/H）；贯穿始终的底座是"item 怎么表示（G）"。

---

## 前传：序列推荐——GR 站在它的肩膀上

GR 的"生成"能力，本质来自"把用户历史当序列建模"。不先讲这段，后面 SID 自回归生成会显得凭空出现。

### GRU4Rec / SASRec / BERT4Rec

- **GRU4Rec**（Hidasi 等，ICLR 2016，[arXiv:1511.06939](https://arxiv.org/abs/1511.06939)）：将 RNN 用于 session 序列推荐的代表作。
- **SASRec**（Kang & McAuley，ICDM 2018，[arXiv:1808.09781](https://arxiv.org/abs/1808.09781)）：用**自注意力**建模用户行为序列，预测下一个 item——这是"用户历史 = 一个序列，next-item = next-token"范式的关键奠基。
- **BERT4Rec**（Sun 等，CIKM 2019，[arXiv:1904.06690](https://arxiv.org/abs/1904.06690)）：把 BERT 的**双向 + 掩码(Cloze)**训练搬到序列推荐。
- **一句话**：把推荐变成"序列上的 next/masked item 预测"，Transformer 成为推荐主干。
- **串联理解**："GR 里的'自回归生成 item'，其实是 SASRec 这条序列建模主线的自然延伸——只不过生成的不再是 item 本身，而是 item 的 Semantic ID。"

---

## 路线 A：基础生成式召回——Semantic ID / Generative Retrieval

GR 的地基。传统检索是 two-tower + ANN（给每个 item 一个向量坐标，找最近邻）。SID 路线的生成式召回把 item 表示成若干离散 token（**Semantic ID, SID**），让模型像生成句子一样逐 token 生成"下一个 item 的地址"。

> **类比**：ANN = 给每个商品一个坐标找附近的；SID 生成 = 给每个商品一个层级邮编（亚洲→中国→北京→某小区），一步步生成邮编。

### TIGER：Recommender Systems with Generative Retrieval

- Rajput 等，**Google，NeurIPS 2023，[arXiv:2305.05065](https://arxiv.org/abs/2305.05065)**。

- **一句话**：用 RQ-VAE 把每个 item 编成层级 Semantic ID，再用 seq2seq Transformer **自回归生成"下一个 item 的 SID"**，开创生成式检索在推荐的范式。
- **解决什么**：ANN 召回要维护 item 向量索引；能不能换成离散索引，直接"生成"目标 item 的地址？
- **怎么做(白话)**：① 用预训练文本 encoder 得 item 内容向量 → ② **RQ-VAE 残差量化**成一串层级 codeword（如 `[12, 7, 93]`）当 SID（语义相近的 item 有机会共享前缀）→ ③ 训练 T5 式模型：输入用户历史 SID 序列，自回归吐出 next item 的 SID；线上用 beam search 生成候选。
- **结果**：多个公开数据集显著超越 SASRec 等；并展现出**冷启动/泛化**潜力（相似内容共享 SID 前缀）。
- **关键 insight**：**把"检索"变成"在小词表上生成层级 token"**——这是后面一切 SID 类 GR 的共同起点。

### PinRec：Unified Generative Retrieval for Pinterest Recommender Systems（工业规模落地）

- Pinterest，2025，[arXiv:2504.10507](https://arxiv.org/abs/2504.10507)。
- **一句话：** 将生成式召回落地到 Pinterest 工业规模，并通过 outcome conditioning 让同一个 GR 模型按 click/save 等不同业务目标生成候选。
- **怎么做：** ① **Outcome-conditioned generation**：将用户行为 outcome（click/save 等）作为生成条件，并通过 serving budget 控制不同目标导向的候选比例；② **Windowed multi-token prediction**：不再要求严格预测唯一的 next item，而允许未来时间窗口内的多个 engagement 作为有效预测目标，模型 forward 之后，根据当前 prediction 对 window 里的所有合法 positive 算 loss，然后动态选 loss 最小的那个。
- **结果：** Pinterest 工业场景线上显著正向，并证明 continuous generative retrieval 可以规模化部署；后续 UniPinRec 在这一体系上进一步统一 retrieval 与 ranking。
- **Insight：** PinRec 实际解决了两个不同问题：**multi-token 放松“next-item prediction”的严格序列假设；outcome conditioning 则让“召回什么”可以由业务目标控制**

> PinRec 走连续向量生成与 ANN 检索路线。生成式召回不只有离散 SID 这一种实现。

---

## 路线 A'：生成式排序 & Scaling Law——生成式架构本身的威力

生成式不只用于召回。另一条并行主线是：**把生成式/序列架构直接用在排序，并验证 Scaling Law**。

### HSTU：Actions Speak Louder than Words

- Zhai 等，**Meta，ICML 2024，[arXiv:2402.17152](https://arxiv.org/abs/2402.17152)**。
- **一句话**：为高基数、非平稳的推荐流式数据设计新生成式架构 HSTU，在大规模推荐实验中验证**模型质量随训练算力变化的幂律关系**（论文报告万亿级参数配置）。
- **解决什么**：推荐能不能像 LLM 一样"越大越强"？传统 DLRM 堆特征天花板明显。
- **怎么做(白话)**：把用户行为（点击、点赞…）拉成一条超长 token 序列，用自研 HSTU（比标准 attention 更省、对长序列更快）做统一的生成式序列转导（Generative Recommenders, GR）。
- **结果**：NDCG 比基线最高 **+65.8%**；8192 长序列上比 FlashAttention2 快 **5.3–15.2x**；**1.5 万亿参数**在线 A/B **+12.4%**，已在十亿级用户平台多场景部署；效果随训练算力呈幂律，扩到 GPT-3/LLaMa-2 量级。
- **关键 insight**：**推荐模型可以呈现经验性的 Scaling Law**；行为序列提供了可扩展的建模对象，但这不意味着所有场景都不再需要手工特征。
- **串联理解**："HSTU 是把'Scaling Law'带进推荐的里程碑——它和 TIGER 是两条地基：TIGER 管'怎么生成候选'，HSTU 管'生成式架构 + 越大越强'。"

### GenRank：Towards Large-scale Generative Ranking

- 小红书，2025，[论文](https://arxiv.org/abs/2505.04180)。
- **核心问题**：生成式排序的收益，到底来自生成式训练目标，还是来自架构如何组织用户与候选物品的交互？
- **主要发现**：论文的理论与实验分析认为，其设置下的主要收益来自生成式架构，而非训练范式本身；据此提出用于大规模排序的 GenRank。
- **工业意义**：在接近原生产系统计算资源的条件下，论文报告了线上用户满意度提升。这说明采用生成式架构并不要求先把召回、排序整条链路全部推翻。
- **阅读重点**：区分“换 backbone”“换训练目标”和“换整个推荐 pipeline”，三者需要分别验证。

---

## 路线 B：全链路 / Full-stack GR——能不能把 cascade 整体替掉

最激进的一条：既然用户历史已被大 Transformer 编码，能不能直接生成最终推荐，把 retrieval/pre-rank/rank 的边界整体重写？

> **易混淆点**："一个模型替掉整个 pipeline" ≠ "模型内部只有一个纯 autoregressive decoder"。2026 反复说明：pipeline 可以统一，但内部仍可能保留 ranking module。

### OneRec：Unifying Retrieve and Rank + Iterative Preference Alignment

- 快手，2025，[arXiv:2502.18965](https://arxiv.org/abs/2502.18965)。
- **一句话**：最具代表性的"终局假设"——用一个生成式 recommender 直接替代 retrieve-and-rank 级联。
- **怎么做**：Encoder-Decoder + Sparse MoE 扩容量；**session-wise generation**一次生成一整组推荐；再用 reward model + **DPO** 做 iterative preference alignment（IPA）。
- **结果**：论文报告在快手实际场景中验证了统一生成与偏好对齐的效果。
- **insight**：把问题从"GR 能不能做召回"升级为"recommendation 能不能直接成为 sequence generation"——2025 后很多统一架构的起点。
- **局限**：没证明"所有行业都适合纯生成"；Ads/电商多目标约束更强，后续论文不断把 ranking specialization 加回来。
- **串联理解**："OneRec 先把终局问题问出来：为什么一定要多阶段？后面的工作基本都在回答——哪些阶段真能删，哪些功能必须以新形式保留。"

### Sona Technical Report（单模型替换成熟级联的公开案例）

- Yandex Music，2026，[arXiv:2608.11015](https://arxiv.org/abs/2608.11015)。
- **一句话**：一个单模型真的替掉了 15+ 候选生成器 + pre-ranking + ranking。
- **怎么做**：用户按时间排列的行为序列经过 shared encoder；SID decoder 通过 autoregressive generation 产生候选，Ranking Module 对生成 item 做 item-level scoring；generation 的 NTP loss 和 ranking 的 teacher-distillation loss **共同更新 Encoder**。因此 user representation 同时学“什么 item 值得生成”和“什么 item 最终应该排得高”。
- **结果**：Yandex Music 智能音箱上的 My Vibe A/B 实验：活跃用户 **+4.53%**、总收听 **+6.30%**、点赞 **+11.42%**。
- **insight**：“Sona 比‘GR 能不能替代 recall’又往前走了一步。它不是只替掉一个召回源，而是把 15+ recall、粗排、精排整套 production cascade 换成一个模型。不过它内部并没有神奇地把 ranking 消失掉——仍然有 SID Generator 和 Ranking Module。真正的统一发生在 shared encoder、joint training 和 single-model serving 上。”

---

## 路线 C：Generation + Ranking 统一——生成不等于排序（2026 最值得关注）

大家逐渐发现：生成 SID 很适合"候选空间搜索"，但 **beam search 的 sequence likelihood 并不天然等于具体 item 的最终价值**。于是 ranking 以更紧耦合的方式回归。

### Gryphon：Semantic-ID Generation + Item-Level Scoring

- Yandex，2026，[arXiv:2606.08604](https://arxiv.org/abs/2606.08604)。
- **一句话**：只生成 SID 不够——先生成候选，再对具体 item 做 item-level scoring。
- **解决什么**：beam search 优化的是 SID 序列 likelihood，不是 item relevance；且多个 item 可能 collision 到同一 SID、拿到相同分。
- **怎么做**：共享 Transformer encoder；一路自回归生成 SID 候选，另一路 Item-Level Scoring Module(ILSM) 直接给 item 打分；共享 user representation 避免重复计算。
- **结果**：item-level Recall@1000 比 vanilla GR **+3.7%**；同批候选上 item-level ranking 比 beam-likelihood **+4.2%**；线上总收听 +0.25%（未显著），但替掉 15+ 候选生成器和单独 prerank。
- **insight**：**SID 的生成分数不天然等于 item 的最终效用**。尤其存在碰撞时，同一个 SID 的概率不能直接区分其对应的多个 item；即使 ID 唯一，拟合历史消费概率也不等于最大化业务目标。
- **串联理解**："Gryphon 是对纯 GR 最直接的结构性修正：生成模型负责找方向，item scorer 负责最后把具体 item 分清楚。"

### UniPinRec：Unifying Generative Retrieval and Ranking at Pinterest Scale

- Pinterest，2026，[arXiv:2606.00422](https://arxiv.org/abs/2606.00422)。
- **一句话**：最工业现实主义的统一——共享 backbone/input/training/serving，但 retrieval 和 ranking 保留不同计算方式。**既然 Retrieval 和 Ranking 都是在理解同一个用户，为什么不能只理解一次？**
- **怎么做**：共享 Transformer user backbone；retrieval 仍走 ANN 点积；ranking 用 candidate-conditioned cross-attention；Masked Action Modeling 联合训练；跨 stage 共享 KV cache。
- **结果**：核心 surface 约 **+1%** 互动；端到端延迟 **-11.1%**；QPS **+63.6%**。
- **insight**：UniPinRec 真正的创新不是“用一个 loss 同时做召回和排序”，而是发现 Retrieval 和 Ranking 一个昂贵且重复的部分是“理解用户历史”，因此把 user modeling 彻底共享，而把 candidate-specific computation 留给各自的 head。

### UniR²：Unifying Generative Recall + Multi-Objective Ranking in One Decoder

- 快手，2026，[arXiv:2607.24439](https://arxiv.org/abs/2607.24439)。
- **一句话**：把 user context、**SID 生成轨迹**、item ranking 特征串成一条异构 decoder-only 序列。让 ranking 直接复用 SID generation trajectory，而不是只接收 Recall 输出的 Item ID。
- **怎么做**：Dual-Query Prefix-Causal Attention 给召回/排序不同可见性；共享 base attention，但 ranking 用 **LoRA + stop-gradient** 保留独立优化边界；SID trajectory 当表示桥梁，以控制 recall 与 ranking 的优化干扰。
- **结果**：论文报告快手平台长期线上 A/B 测试取得正向收益。
- **insight**：UniR² 真正前进的一步不是“共享一个 Transformer”，而是让 Recall 的 generation trajectory 成为 Ranking 的显式中间表示——Recall → Rank 之间传递的不再只是 Item ID。这与 UniPinRec 主要共享用户历史计算的切入点不同。

### UniSGR：电商版生成+多目标 ranking 统一

- Alibaba/Lazada，2026，[arXiv:2607.04068](https://arxiv.org/abs/2607.04068)。
- **一句话**：不仅找相关商品，还要对 click/转化/GMV 等价值目标对齐；multi-scenario pretraining + scenario-specific alignment。
- **insight**：**ranking signal 不会因 GR 消失，而是越来越早进入 generation/representation 学习**。

---

## 路线 D：多目标 / 可控 GR——不是一个 decoder 管所有目标

工业推荐几乎从不是单目标。GR 若只有一个 next-token objective，容易把所有 policy 混在一起。

### Multi-Decoder OneRec：Controllable GR for Multi-Objective

- 快手，2026，[arXiv:2607.26500](https://arxiv.org/abs/2607.26500)。
- **一句话**：共享一个生成 backbone，但给不同业务目标各配 LoRA expert / decoder policy，并显式控制各路 quota。
- **怎么做**：User Context 与 General Decoder 共享；Long-view、Cold-start 等目标各自增加 isolated LoRA expert，并通过 gradient routing 隔离更新；Watch-time 目标使用 KL-regularized policy optimization。推理时给各目标显式分配 quota，再通过 **Multi-Decoder Constrained Beam Search** 避免不同 decoder 重复召回相同 SID，General Decoder 最后补齐剩余预算。
- **结果**：同 512 召回预算下四项 Recall@512 比单 decoder **+1.69%\~5.62%**；线上使用时长 +0.37%、D7 留存 +0.19%、冷启内容 +2.09%。
- **insight**：GR 的“统一”不应该以牺牲 retrieval policy 的可控性为代价。最合理的统一可能不是 one policy，而是 shared representation + objective-specific policies。

### OneRanker：广告场景的生成+价值排序统一

- 腾讯/微信广告，2026，[arXiv:2603.02999](https://arxiv.org/abs/2603.02999)。
- **一句话**： 广告推荐不能只生成“用户最可能感兴趣”的 item，因为最终目标还有 GMV 等商业价值；OneRanker 在一个模型中把 **interest-oriented generation** 与 **value-oriented ranking** 连起来，让“召得准”和“排得值钱”协同优化。
- **怎么做**： ① **Value-aware multi-task decoupling**：task token + causal mask 隔离兴趣覆盖与价值目标，减少优化冲突；② **coarse-to-fine target awareness**：generation 用 Fake Item Tokens 获得粗粒度 target awareness，ranking decoder 再做 candidate-level 显式 value alignment；③ **KV pass-through + Distribution Consistency Loss** 保留 generation → ranking 的信息并约束两阶段一致性。
- **结果**：微信视频号广告全量，**GMV +1.34%**。
- **insight**：**Semantic relevance ≠ industrial value**——越靠近广告/电商，越不能只靠"生成最相关 item"。

### OGR：Once Generated, Ranked——生成有序 slate

- 快手，2026，[arXiv:2608.17613](https://arxiv.org/abs/2608.17613)。
- **一句话**：不再“先生成候选、再对候选排序”，而是把**有序 slate 本身作为生成对象**，直接联合建模“选哪些 item + 放在哪个位置 + item 之间如何搭配”。
- **怎么做**：**TUSID** 融合 item semantic 与 local collaborative information；**list-wise preference planning** 先建模整张 slate 的全局偏好，再通过 **position-wise SID decoding** 逐位置生成有序列表、显式考虑跨 item/位置依赖；最后用 reward-guided **SPA** 做 conservative policy optimization，使训练目标从 likelihood imitation 进一步对齐 slate-level preference。
- **结果**：NDCG@5 相对 **+48.2%/+27.2%**（工业/公开）；快手 Effective Views **+1.120%**。
- **insight**：**推荐的自然决策单位可能不是 item，而是 slate**；生成模型对"整列表联合建模"有天然优势。
- **串联理解**："如果 Gryphon 在问'生成后要不要再排'，OGR 反过来问：能不能一开始就生成一个已经有序的列表？"

---

## 路线 E：Preference Alignment / RL——从 likelihood 到真实 utility。

NTP 学的是 logged behavior distribution：什么 item 在历史 policy 下被用户消费；Preference Alignment 则进一步问：在当前用户状态下，模型应该生成什么，才能最大化目标 utility。

- **OneRec**：reward model + **DPO**，解决推荐里没有天然正负 pair 的偏好对齐。
- **Multi-Decoder OneRec**：Watch-time expert 用 KL-正则 policy optimization + gradient routing。
- **OGR**：对整个 slate 用 reward-guided conservative policy optimization。
- **怎么理解**：传统推荐像"预测"（会不会点）；GR+alignment 像"决策"（在当前用户状态与约束下，生成哪个候选/slate 能提升目标 utility；是否改善长期价值，还取决于 reward 设计与验证）。
- **提醒**：RL 会放大 reward hacking / off-policy bias / 线上风险——alignment 不是"加个 reward 就完事"。

---

## 路线 F：Reasoning-enhanced Recommendation

把 LLM 的语义与推理能力带进推荐。核心不是"推荐也写 CoT"，而是：能否用显式 reasoning / 语义知识补足纯 ID 协同信号（尤其冷启、复杂意图、可解释）。

### OneRec-Think：In-Text Reasoning for GR

- 快手，2025 年预印本，[arXiv:2510.11639](https://arxiv.org/abs/2510.11639)。
- **为什么需要推理**：“看 NBA → 看 Curry → 看 Warriors → 推荐 NBA 视频” 通常能从协同信号中学到；“最近想去日本，预算不高，不喜欢太热门的地方”则更可能受益于语义知识和约束推理。
- **问题**：LLM 和 Item ID 缺少天然的语义对应关系。
- **怎么做**：
  - Item-Textual Alignment 做跨模态 grounding，把 SID 和多模态语义对应起来；
  - Reasoning Scaffolding 给模型一些推荐场景中的 reasoning demonstrations 让模型学习；
  - 推荐偏好具有多解性，因此使用推荐特定的 reward，避免把所有非唯一标答的候选都视作错误。
  - Think-Ahead 面向工业部署。不要等 request 来了以后才现场长 CoT，把一部分 user reasoning / preference understanding **提前算**，线上 request 来的时候复用已经获得的 reasoning information。

- **结果**：快手 APP Stay Time **+0.159%**。
- **insight**：Reasoning 对推荐最大的潜在价值可能不是“解释已经做出的推荐”，而是把 collaborative signal 难以表达的语义知识、复杂意图和约束显式注入推荐决策；工业上的关键则是如何避免每次请求都支付长 CoT 的成本。

### TGR：Generation、Ranking 与 Reasoning 的工业组合

- 腾讯，2026 年 9 月，[论文](https://arxiv.org/abs/2609.00986)。
- **一句话**：同时推进排序架构、端到端生成和推理增强，并通过离线生成的 reason tokens 控制请求时延。
- **GenRank 路线**：CCFormer 升级 Transformer 排序骨干，仍然保留逐 item 的多任务输出。这里的 TGR-GenRank 是腾讯框架中的路线名，与上文小红书的 GenRank 工作应区分。
- **GenRec 路线**：BARGE 处理层级 SID 生成中的 item 边界与语义漂移；HiGR 面向整张 slate 做由粗到细的生成和多目标对齐。
- **Reason 路线**：将离线生成的 Semantic-ID reason tokens 注入线上解码，让推荐使用推理信息，而无需每次请求都执行推理 rollout。
- **关键启发**：工业系统可以分别选择“怎样建模”“生成什么”和“什么时候做推理”。共享用户理解，不要求所有在线决策都经过同一个纯生成流程。

---

## 路线 G：SID / Tokenizer / Representation——item 的"语言"也要学

GR 效果高度依赖 item tokenization。常见做法：先 RQ-VAE/聚类得 SID，再训 recommender。但有个根本矛盾：**SID 常为内容重构优化，recommender 为用户行为优化，两者目标未必一致**。

- **源头**：RQ-VAE（Lee 等，CVPR 2022，[arXiv:2203.01941](https://arxiv.org/abs/2203.01941)，本是图像残差量化）→ 被 **TIGER** 借来做 item SID。

### DIGER：Differentiable Semantic ID for GR

- 2026，[arXiv:2601.19711](https://arxiv.org/abs/2601.19711)。
- **一句话**：不再把 SID 当预先固定的索引，而是让 recommendation gradient 直接影响 SID 学习。
- **怎么做**：
  - DIGER 的核心就是让 assignment **可微**，differentiable semantic indexing 让推荐 loss 影响 code assignment；
  - Gumbel noise 促早期 code 探索并逐步衰减，防 codebook collapse。

- **insight**：**SID 不是基建细节，而是模型的一部分**——未来 tokenizer 可能和 recommender 联合训练。
- **工程追问**：联合训练时 item→SID 映射会随参数变化。部署需要固定并版本化 tokenizer、codebook 与检索映射；新 item 能否通过冻结 tokenizer 有效进入推荐，还需验证其表示质量、索引更新和模型泛化能力。

**SID 路线的工程难题**：Collision（多 item 同 SID）、Codebook collapse/利用率、Drift（内容/兴趣变了 SID 语义过时）、Churn/freshness（新 item 快速拿稳定 SID、旧 item 删除后维护）、Multimodal（文/图/视/音共同决定 token）、Recommendation-aware tokenization（tokenizer 该不该被下游 utility 训练）。

---

## 路线 H：Multi-domain / Foundation Recommender

平台有 Feed/Search/Ads/Shop/Live 多业务时，问题从"一个场景怎么做 GR"变成：能否共享一个 user intelligence / foundation backbone，同时保留各业务专门化？

### MBGR：Multi-Business GR at Meituan

- 美团，2026，[arXiv:2604.02684](https://arxiv.org/abs/2604.02684)。
- **怎么做**：Business-aware SID(BID) 保留不同业务语义；Multi-Business Prediction 提供业务-specific 预测；Label Dynamic Routing 把稀疏多业务标签变成更密集学习信号。
- **insight**：跨业务共享不是"数据混一起"——共享 user intelligence 的同时要**显式建模 domain identity 与目标差异**。

**我的判断：一种值得关注的架构方向**是 **Recommendation Foundation Backbone + Specialized Decision Heads**。共享：user sequence / representation / 预训练语料 / item 语义 / KV state / serving 基建；专门化：候选搜索 / item 判别 / 多目标打分 / 业务价值对齐 / slate 约束。**最终最值得共享的，可能是 retrieval 和 ranking 背后的用户理解。**

---

## 如果只精读 10 篇（推荐顺序）

1. [TIGER](https://arxiv.org/abs/2305.05065)：生成式检索与 SID 地基。
2. [HSTU](https://arxiv.org/abs/2402.17152)：序列转导架构与 Scaling。
3. [OneRec](https://arxiv.org/abs/2502.18965)：统一召回、排序与偏好对齐。
4. [PinRec](https://arxiv.org/abs/2504.10507)：连续向量生成与 outcome conditioning。
5. [Gryphon](https://arxiv.org/abs/2606.08604)：生成分数为什么不能代替 item 打分。
6. [UniPinRec](https://arxiv.org/abs/2606.00422)：共享用户历史计算与服务缓存。
7. [UniR²](https://arxiv.org/abs/2607.24439)：生成轨迹共享与优化边界。
8. [Multi-Decoder OneRec](https://arxiv.org/abs/2607.26500)：多目标隔离和召回配额控制。
9. [OGR](https://arxiv.org/abs/2608.17613)：有序 slate 生成与整体偏好。
10. [TGR](https://arxiv.org/abs/2609.00986)：generation、ranking、reasoning 的组合。

> 前两篇建立地基，后八篇串联 2025–2026 年的工业演进。路线是理解问题的分类，不是严格的发表先后关系。

## 术语表

- **SID / Semantic ID**：把 item 编成多级离散 token（如 `[12, 7, 93]`），按层级生成。
- **NTP**：Next Token Prediction，GR 的基础训练目标。
- **RQ-VAE**：残差量化 VAE，把内容向量层层量化成 codeword，得到层级 SID。
- **Beam Search**：生成时并行保留若干最可能路径。
- **Collision**：多个 item 落到同一 SID，生成分难区分。
- **ANN**：近似最近邻，传统向量召回。
- **KV Cache**：缓存历史 token 的 Key/Value，避免重算。
- **DPO**：Direct Preference Optimization，用偏好 pair 直接调策略，省掉传统 RL reward loop。
- **Slate**：一次请求最终展示的一组有序 item。
- **LoRA**：低秩适配，在共享 backbone 上给不同任务少量独立参数。
- **Stop-gradient**：前向共享表示，但某 loss 的梯度不更新特定共享参数。

## 延伸阅读

- [[semantic-id-foundations|Semantic ID：生成式推荐的词表]]
- [[tiger-generative-retrieval|TIGER：生成式检索的起点]]
- [[onerec-unified-recommendation|OneRec：统一召回与排序]]
- [[reasoning-for-recommendation|推荐模型真的需要推理吗]]
