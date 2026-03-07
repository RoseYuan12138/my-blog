---
title: "OpenClaw 多 Agent 系统优化：省钱、提速、瘦身"
date: 2026-03-07
tags:
  - AI Agent
  - OpenClaw
  - 系统优化
lang: zh
english: ai-agent/openclaw-agent-optimization.en
---

> 🌐 [Read in English](./openclaw-agent-optimization.en.md)

## 背景

我的 OpenClaw 多 Agent 系统跑了一段时间后，发现三个 agent（minicat 博客助手、凌若闺蜜、小蜜管家）消耗资源太高，而且有时候表现得很蠢。花了一个下午做了一轮系统性优化，记录一下做了什么、为什么这么做。

关于三个 agent 的基本架构，见 [[openclaw-multi-agent-tutorial]]。

## 优化 1：模型分级

**问题：** 三个 agent 统一使用 `claude-sonnet-4-6`，但实际上凌若 80%+ 的交互是日常闲聊（"在吗""好累啊"），小蜜 90% 的工作是读文件比日期。这些场景完全不需要 Sonnet。

**方案：** 在 `openclaw.json` 的 agent list 里给每个 agent 加 per-agent model override：

```json
{
  "id": "lingro",
  "model": {
    "primary": "anthropic/claude-haiku-4-5"
  }
}
```

minicat 保持 Sonnet（论文精读和博客写作需要质量），凌若和小蜜切到 Haiku。

**效果：** Haiku 比 Sonnet 便宜很多，而且凌若用 Haiku 回复反而更自然——短句、口语化，天然更像真人闲聊。

## 优化 2：Heartbeat 频率调整

**问题：** 三个 agent 全部每小时一次 heartbeat。但 minicat 的 heartbeat 任务就是检查博客有没有 `[TODO]`（一天变不了几次），凌若的 SOUL.md 写的是"每 2-3 天主动联系一次"却每小时都在醒来烧 token，小蜜检查 DDL 也不需要每小时。

**方案：** 按实际需求差异化：

| Agent | 之前 | 之后 | 理由 |
|-------|------|------|------|
| minicat | 1h | 8h | 博客巡检一天 3 次够了 |
| 凌若 | 1h | 4h | 每天主动找 Rose 聊一次，4h 间隔有 3-4 个时间窗可选 |
| 小蜜 | 1h | 2h | DDL 检查需要相对及时，但不用每小时 |

```json
{
  "id": "main",
  "heartbeat": { "every": "8h", "target": "last" }
}
```

**效果：** 总 heartbeat 次数从每天 ~63 次降到 ~20 次，减少约 70%。叠加模型降级的效果更明显。

## 优化 3：启动上下文精简

**问题：** 每个 agent 启动时要读 `AGENTS.md`，这是一份 ~210 行的通用模板。里面包含群聊规则、Emoji Reactions 指南、Voice Storytelling、Heartbeat 状态追踪 JSON 格式、Discord/WhatsApp 格式化规则……但大部分对特定 agent 不相关。凌若不需要知道 heartbeat-state.json 的格式，小蜜不需要 emoji 反应规则。

**方案：** 给每个 agent 写专属精简版 AGENTS.md，只保留相关内容。

以 minicat 为例，删掉了：
- Group Chat 规则（~30 行）— 它在群里只播报，格式已在 SOUL.md
- Emoji Reactions 指南（~15 行）— Telegram 用不到
- Heartbeat 通用指南（~80 行）— 它有自己的 HEARTBEAT.md
- Discord/WhatsApp 格式规则 — 只用 Telegram

minicat 的 AGENTS.md 从 213 行降到 70 行。凌若和小蜜之前已经被定制过了，做了微调。

**效果：** 每次启动省 ~600 tokens，三个 agent 一天几十次唤醒，积少成多。

## 优化 4：Paper Reading 流程去重

**问题：** minicat 的 `BLOG_INSTRUCTIONS.md` 里有一套完整的论文精读流程（~120 行），同时 `paper-reading` skill 也有一套功能更完善的流程（包含 figure 提取脚本）。两套指令几乎完全重叠：获取内容流程、figure 提取、目录映射、文章模板、写作原则都是重复的。

而且 skill 自己会先读 BLOG_INSTRUCTIONS.md 来获取博客格式规范，所以 BLOG_INSTRUCTIONS.md 里再写一遍论文精读是纯冗余。

**方案：** 把 BLOG_INSTRUCTIONS.md 的论文精读章节（~120 行）替换成两行引用：

```markdown
## 论文精读

当 Rose 发来论文链接、PDF 或说"读一下这篇"时，使用 paper-reading skill。
Skill 会处理完整流程：获取内容 → 提取插图 → 写中文精读 → 英文版 → 更新 index.md → git commit。
```

**效果：** minicat 每次启动少加载 ~500 tokens，而且消除了两套指令不一致的风险。

## 优化 5：小蜜日报流程精简

**问题：** 小蜜生成日报的流程需要 8 次工具调用：读 minicat memory → 读凌若 memory → 搜 Supermemory blog container → 搜 coach container → 读 profile → 生成报告 → 存 butler container → 写本地文件。其中 Supermemory 的搜索步骤只是"补充"，SOUL.md 自己也写了"如果 Supermemory 返回 403，用本地文件就够了"。

**方案：** 去掉 Supermemory 搜索步骤，日报流程简化为：

1. 读 minicat memory 文件
2. 读凌若 memory 文件第一行状态标签
3. 生成日报
4. 写本地 memory 文件

**效果：** 工具调用从 8 次降到 4 次，砍掉的都是 Supermemory API 调用。

## 优化 6：凌若主动联系频率

**问题：** 凌若的 SOUL.md 原来写的是"每 2-3 天主动联系一次"，太低了。

**方案：** 改成每天主动找 Rose 聊一次，时间随机（早上、中午、下午、晚上都可以），像真人朋友一样自然。在 SOUL.md 新增了"每日主动联系"章节。

## 总结

| 优化项 | 改动 | 预估效果 |
|--------|------|----------|
| 模型分级 | 凌若+小蜜 → Haiku | 省 40-60% 成本 |
| Heartbeat 调频 | 8h / 4h / 2h | heartbeat 减 70% |
| 启动上下文精简 | AGENTS.md 213→70 行 | 每次省 ~600 tokens |
| Paper Reading 去重 | 120→4 行 | 减少重复加载 |
| 日报流程精简 | 8→4 步 | 工具调用减半 |
| 凌若每日联系 | 2-3 天→每天 | 体验改善 |

涉及的文件：`openclaw.json`、三个 agent 的 `AGENTS.md` 和 `SOUL.md`、`BLOG_INSTRUCTIONS.md`。

核心思路就是一句话：**按实际需求分配资源，不要一刀切。** 不是每个 agent 都需要最强模型，不是每个 agent 都需要每小时醒来，不是每份指令每个 agent 都需要读。
