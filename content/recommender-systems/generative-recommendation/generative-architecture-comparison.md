---
title: "生成式推荐架构对比：Encoder–Decoder、Lazy Decoder 与 Decoder-Only"
date: 2026-08-29
tags:
  - 推荐系统
  - 生成式推荐
  - Decoder-Only
  - Beam Search
lang: zh
---

生成式推荐的输入通常很长：用户历史可能有数百或数千个 Token；输出却很短：一个 SID 常只有几层。不同架构的主要差异，就是如何在“长输入、短输出、Beam Search”下复用计算。

## Encoder–Decoder

Encoder 双向编码完整历史，Decoder 通过 Cross-Attention 逐步生成 SID。

优势是输入理解与输出生成职责清晰，历史表示可在 Beam 之间共享。缺点是需要两套网络，并承担 Cross-Attention 和缓存管理。

## Lazy Decoder

Lazy Decoder 尽量把用户历史提前压成少量状态，只有生成阶段才运行较重的 Decoder。它适合输出很短、Beam 较宽的场景，可以减少重复计算。

风险在于历史被过早压缩；如果摘要没有保留某个兴趣方向，后续生成无法恢复。

## Decoder-Only

把用户历史和目标 SID 拼成一个因果序列：

```text
[用户历史 Token] [分隔符] [SID-1] [SID-2] [SID-3]
```

结构统一，也便于复用 LLM 训练技术。看起来完整历史参与自注意力会更贵，但实际成本取决于 KV Cache 和 Beam 阶段。如果主要算力消耗在多分支解码，统一 Decoder 反而可能更高效。

## 如何选择

- 历史很长且希望充分双向建模：Encoder–Decoder 更自然。
- 输出极短、在线预算严格：Lazy Decoder 值得优先评估。
- 希望统一训练范式、使用多 Token 预测或继续 Scaling：Decoder-Only 更简洁。

## 不要只比较 FLOPs

需要按完整 Serving 链路测量：历史编码能否跨候选复用、Beam 扩展是否复制状态、KV Cache 大小、批处理效率、合法 Token 掩码成本和 Tail Latency。

推荐场景没有永远最优的生成架构。真正决定答案的是输入长度、输出深度、Beam 宽度和缓存复用方式。
