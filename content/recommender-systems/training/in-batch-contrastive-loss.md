---
title: "搜索 vs 推荐：In-Batch Contrastive Loss 的场景差异"
date: 2026-03-01
tags:
  - 推荐系统
  - 对比学习
  - Contrastive Loss
  - 双塔模型
  - Session Mask
lang: zh
english: recommender-systems/training/in-batch-contrastive-loss.en
---

> 🌐 [Read in English](./in-batch-contrastive-loss.en.md)

In-Batch Softmax Contrastive Loss 在搜索场景已经是标准做法——双塔编码 query 和 doc，batch 内交叉打分，softmax cross entropy 拉近正样本、推远负样本。但把这套方案迁移到推荐场景时，会发现两个场景在数据结构上有根本差异，直接照搬会踩坑。本文梳理这些差异，以及它们如何影响正负样本选择和 session mask 的设计。

---

## 一、背景：In-Batch Contrastive Loss 做了什么

简单回顾：一个 batch 内有 B 条 (user, item) 配对，分别编码后算 B×B 的相似度矩阵。对角线是真实配对，其余位置天然充当负样本。对每行做 softmax cross entropy，让正确配对的相似度高于错误配对。

这套方法的核心优势是**不需要额外构造负样本**，batch 内其他样本的 item 天然就是负样本，batch 越大负样本越多，信号越充分。

最终目的不是 contrastive loss 本身，而是**产出高质量的语义 embedding**，注入下游精排模型提升 CTR。

---

## 二、数据结构的根本差异

**搜索场景：同一个 query 对应多个 doc。**

一次搜索请求返回多条结果，用户点了一些没点一些，产生多条训练样本。这些样本的 query 完全相同，只是 doc 不同：

```
query="王者荣耀" → doc_0="张大仙王者教学"  label=1
query="王者荣耀" → doc_1="王者荣耀攻略"    label=0
query="王者荣耀" → doc_2="王者荣耀皮肤"    label=0
```

**推荐场景：每条样本通常来自不同用户。**

推荐的训练数据按 (user, item) 配对，不同用户的请求混在一个 batch 里：

```
用户A → item_0(王者)  label=1
用户B → item_1(化妆)  label=0
用户C → item_2(吃鸡)  label=1
```

这个差异看似简单，却直接影响了正负样本选择和 session mask 两个关键设计。

---

## 三、正负样本选择：搜索只选正样本，推荐正负都参与

### 搜索为什么只选正样本

上面的搜索例子中，三条样本的 query 完全一样，User 编码器对它们产出几乎相同的 user_output。如果三条都参与 contrastive loss，相似度矩阵会出现多行几乎一模一样的情况：

```
              doc_0    doc_1    doc_2    ...其他doc
user_0(王者)   0.9      0.85     0.8     0.1
user_1(王者)   0.9      0.85     0.8     0.1   ← 和上面几乎一样
user_2(王者)   0.9      0.85     0.8     0.1   ← 和上面几乎一样
```

重复行导致梯度互相干扰——user_0 那行要推高 doc_0 推低 doc_1，但 user_1 那行 label=0 不推高 doc_1，两行的 user_output 几乎一样却要学不同的目标。

所以搜索的做法是**只保留正样本**，每个 query 只出现一次。过滤后矩阵里没有重复行，信号干净。负样本全部来自其他 query 的正样本 doc。

### 推荐为什么正负都可以参与

推荐场景中每条样本来自不同用户，user_output 各不相同，不存在重复行的问题。负样本的 item 天然是好的对比对象——不同品类的 item 提供强区分信号，正负样本都参与信号更充分。

---

## 四、Session Mask：同一个问题，不同的解法

搜索和推荐面对的是同一个问题：**同一个用户同一次请求的多个正样本不能互相当负样本。**

用户 A 搜"王者荣耀"，点了张大仙也点了梦泪，这两个 doc 对用户 A 来说都是正确结果。如果让它们互相当负样本，模型会收到矛盾的梯度——一边要推高张大仙，一边要推低梦泪，但两个都是对的。

两个场景解决这个问题的方式不同：

**搜索：一刀切——只选正样本。** 同一个 query 下只保留一条正样本，其余全部踢掉（包括负样本）。简单粗暴但够用，负样本来自其他 query 的 doc，不缺对比信号。

**推荐：精细化——Session Mask。** 推荐不能简单踢掉负样本（负样本也要参与对比），所以用 session mask 只屏蔽同一 request 内的其他正样本，其余位置保留。

以推荐场景为例，用户A 的一次请求产生 4 条样本：

```
req_1, 用户A → item_0(王者)  label=1
req_1, 用户A → item_1(吃鸡)  label=1
req_1, 用户A → item_2(美妆)  label=0
req_1, 用户A → item_3(舞蹈)  label=0
```

对于样本0（用户A → item_0），session mask 的处理：

- item_1：同 request + 正样本 → **mask 掉**（用户A也点了，不能当负样本）
- item_2：同 request + 负样本 → **保留**（用户A没点，正常当负样本）
- item_3：同 request + 负样本 → **保留**（用户A没点，正常当负样本）
- 其他 request 的所有 item → **保留**（不同用户，不存在矛盾）

被 mask 的位置分数设为 -1e9，在 softmax 时概率接近 0，既不当正样本也不当负样本。

### 什么时候需要 mask，什么时候不需要

判断标准很简单——**只有同一用户、同一请求、双方都是正样本时才需要 mask**：

- 同一用户、同一请求、都是正样本 → **mask**。user_output 完全一样，互相当负样本产生矛盾梯度。
- 同一用户、同一请求、一正一负 → **不 mask**。负样本就是用户没点的，当负样本没问题。
- 同一用户、不同请求 → **不 mask**。两次请求间用户状态可能已变（历史序列更新），是独立的推荐决策。
- 不同用户 → **不 mask**。不管是否喜欢同品类，user_output 不同就不存在矛盾。Contrastive loss 学的是相对排序，不是绝对好坏。

### 没有 request_id 时

如果训练数据暂时没有 request_id，正确做法是**不做任何 mask**（session_mask 全为 False）。一个常见的错误是把所有样本的 session_id mock 成同一个值，这会让系统认为所有样本来自同一次请求，所有正样本互相 mask，对比信号全部丧失。

---

## 五、正负样本来源对比

| | 搜索（只选正样本后） | 推荐（使用 Session Mask） |
|--|---------------------|--------------------------|
| **正样本** | 当前 query 的正样本 doc（对角线，1个） | 当前 user 当前 request 的正样本 item（对角线，1个） |
| **负样本** | 其他 query 的正样本 doc | 同 request 负样本 + 其他用户的正样本 + 其他用户的负样本 |
| **不参与 loss** | 同 query 的其他样本（直接踢掉） | 同 request 的其他正样本（session mask 掉） |

推荐场景的负样本来源更丰富。搜索过滤后只剩"其他 query 的正样本 doc"，而推荐保留了同 request 内用户未点击的 item 以及其他用户的所有 item。

---

## 六、语义关联强度的差异

另一个值得注意的差异是 user 和 item 之间的语义关联强度。

**搜索是直接匹配。** query="王者荣耀直播"，doc="张大仙王者荣耀教学直播间"，两段文本说的就是同一件事，语义编码器很容易学到这种匹配。

**推荐是间接推理。** user 侧是一段历史行为序列（如用户过去看过的多个 item 的文本），item 侧是候选 item 的文本。模型需要从 ["吃鸡决赛圈", "英雄联盟排位教学", "原神攻略"] 这样的历史中推断出"游戏用户"，再和候选 "王者荣耀上分技巧" 匹配。这个信号比搜索弱不少。

这意味着 contrastive loss 在推荐场景更适合作为**辅助 loss**，和主 CTR loss 联合训练，给 embedding 增加语义对齐的正则信号，而不是期望它单独带来搜索场景那样的大幅提升。

如果语义信号确实太弱，可以考虑缩短历史序列（只用最近几个 item，兴趣更聚焦）、按品类过滤 user 侧历史、或使用 hard negative mining 增强区分度。

---

## 七、总结

| | 搜索 | 推荐 |
|--|------|------|
| 数据结构 | 同一 query 对应多个 doc | 不同用户混合在 batch 中 |
| 正负样本选择 | 只选正样本（避免重复 query 干扰） | 正负都参与（不存在重复 user 问题） |
| 同 session 多正样本处理 | 一刀切踢掉 | Session Mask 精细化屏蔽 |
| 负样本来源 | 其他 query 的正样本 doc | 同 request 负样本 + 其他用户所有样本 |
| 语义关联强度 | 强（query-doc 直接匹配） | 较弱（用户兴趣-候选 间接推理） |
| Contrastive Loss 定位 | 核心训练目标 | 辅助 loss，配合主 CTR loss |
