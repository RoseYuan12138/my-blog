---
title: "OpenClaw Multi-Agent Optimization: Cost, Speed, and Context"
date: 2026-03-07
tags:
  - AI Agent
  - OpenClaw
  - Optimization
lang: en
chinese: ai-agent/openclaw-agent-optimization
---

> 🌐 [中文版](./openclaw-agent-optimization.md)

## Background

After running my OpenClaw multi-agent system for a while, I noticed the three agents (minicat for blogging, 凌若 as an emotional companion, 小蜜 as a butler/coordinator) were burning through resources while sometimes being surprisingly dumb. Spent an afternoon doing a systematic optimization pass — here's what I changed and why.

For the basic architecture of the three agents, see [[openclaw-multi-agent-tutorial]].

## Optimization 1: Model Tiering

**Problem:** All three agents used `claude-sonnet-4-6` uniformly, but 80%+ of 凌若's interactions are casual chat ("hey" "so tired"), and 90% of 小蜜's work is reading files and comparing dates. These don't need Sonnet.

**Solution:** Add per-agent model overrides in `openclaw.json`:

```json
{
  "id": "lingro",
  "model": {
    "primary": "anthropic/claude-haiku-4-5"
  }
}
```

minicat stays on Sonnet (paper reading and blog writing need quality), 凌若 and 小蜜 switch to Haiku.

**Result:** Haiku is much cheaper than Sonnet, and 凌若 actually sounds more natural on Haiku — shorter sentences, more colloquial tone, which fits her "real friend" persona better.

## Optimization 2: Heartbeat Frequency

**Problem:** All three agents had heartbeat set to every hour. But minicat's heartbeat task is just checking for `[TODO]` items in blog posts (barely changes daily), 凌若's SOUL.md said "reach out every 2-3 days" yet she was waking up every hour burning tokens, and 小蜜's DDL checks don't need hourly polling either.

**Solution:** Differentiate by actual need:

| Agent | Before | After | Rationale |
|-------|--------|-------|-----------|
| minicat | 1h | 8h | Blog inspection 3x/day is enough |
| 凌若 | 1h | 4h | Daily proactive contact, 4h gives 3-4 time windows to choose from |
| 小蜜 | 1h | 2h | DDL checks need to be timely but not hourly |

```json
{
  "id": "main",
  "heartbeat": { "every": "8h", "target": "last" }
}
```

**Result:** Total heartbeats dropped from ~63/day to ~20/day, a ~70% reduction. Combined with the model downgrade, the cost savings multiply.

## Optimization 3: Startup Context Trimming

**Problem:** Each agent loads `AGENTS.md` on startup — a ~210-line generic template containing group chat rules, emoji reaction guidelines, voice storytelling instructions, heartbeat state tracking JSON format, Discord/WhatsApp formatting rules... Most of it irrelevant to any specific agent. 凌若 doesn't need to know heartbeat-state.json format, 小蜜 doesn't need emoji reaction rules.

**Solution:** Write agent-specific slimmed-down versions of AGENTS.md, keeping only relevant sections.

For minicat, removed:
- Group Chat rules (~30 lines) — it only broadcasts in groups, format already in SOUL.md
- Emoji Reactions guide (~15 lines) — not needed for Telegram
- Generic Heartbeat guide (~80 lines) — it has its own HEARTBEAT.md
- Discord/WhatsApp formatting — only uses Telegram

minicat's AGENTS.md went from 213 to 70 lines. 凌若 and 小蜜 were already customized, just minor tweaks.

**Result:** ~600 tokens saved per startup, across dozens of daily wake-ups.

## Optimization 4: Paper Reading Deduplication

**Problem:** minicat's `BLOG_INSTRUCTIONS.md` contained a full paper reading pipeline (~120 lines), while the `paper-reading` skill had its own more complete pipeline (including figure extraction scripts). The two sets of instructions were nearly identical: content fetching, figure extraction, directory mapping, article template, writing principles — all duplicated.

The skill itself reads BLOG_INSTRUCTIONS.md for blog conventions on Step 0, so having paper reading instructions in BLOG_INSTRUCTIONS.md was pure redundancy.

**Solution:** Replace the ~120-line paper reading section with a two-line reference:

```markdown
## 论文精读

当 Rose 发来论文链接、PDF 或说"读一下这篇"时，使用 paper-reading skill。
Skill 会处理完整流程：获取内容 → 提取插图 → 写中文精读 → 英文版 → 更新 index.md → git commit。
```

**Result:** ~500 fewer tokens loaded per minicat startup, plus elimination of inconsistency risk between two instruction sets.

## Optimization 5: Butler Daily Report Streamlining

**Problem:** 小蜜's daily report required 8 tool calls: read minicat memory → read 凌若 memory → search Supermemory blog container → search coach container → read profile → generate report → store to butler container → write local file. The Supermemory searches were just "supplements," and her own SOUL.md said "if Supermemory returns 403, local files are enough."

**Solution:** Remove Supermemory search steps, simplify to:

1. Read minicat's memory file
2. Read 凌若's memory file (first line status tag only)
3. Generate report
4. Write local memory file

**Result:** Tool calls cut from 8 to 4, all removed calls were Supermemory API calls.

## Optimization 6: 凌若 Proactive Contact Frequency

**Problem:** 凌若's SOUL.md originally said "proactively reach out every 2-3 days" — too infrequent for a close friend.

**Solution:** Changed to once daily at a random time (morning, afternoon, or evening), making it feel natural rather than scheduled. Added a "daily proactive contact" section to her SOUL.md.

## Summary

| Optimization | Change | Estimated Impact |
|-------------|--------|-----------------|
| Model tiering | 凌若+小蜜 → Haiku | 40-60% cost reduction |
| Heartbeat tuning | 8h / 4h / 2h | 70% fewer heartbeats |
| Context trimming | AGENTS.md 213→70 lines | ~600 tokens/startup saved |
| Paper reading dedup | 120→4 lines | Reduced redundant loading |
| Report streamlining | 8→4 steps | Halved tool calls |
| Daily contact | 2-3 days → daily | Better experience |

Files changed: `openclaw.json`, each agent's `AGENTS.md` and `SOUL.md`, `BLOG_INSTRUCTIONS.md`.

The core principle is simple: **allocate resources by actual need, don't one-size-fits-all.** Not every agent needs the strongest model, not every agent needs hourly wake-ups, not every instruction needs to be loaded by every agent.

## Bonus: Installing ClawHub Skills

After optimizing resource consumption, I also installed two community skills to make the agents smarter:

### self-improving-agent

A community skill from [ClawHub](https://clawhub.com). It automatically captures agent mistakes, user corrections, and knowledge gaps, logging them to a `.learnings/` directory in the workspace (`LEARNINGS.md`, `ERRORS.md`, `FEATURE_REQUESTS.md`). High-value learnings can be promoted to SOUL.md or AGENTS.md, becoming permanent knowledge.

Installed for all three agents. The goal is to solve the "agent makes the same mistake twice" problem — for example, if 凌若 speaks too much like an AI and gets called out, she can automatically remember not to use that tone again.

Installation:

```bash
cd /Users/minicat/.openclaw/workspace
clawhub install self-improving-agent

# Other agents
clawhub install self-improving-agent --workdir /Users/minicat/.openclaw/lingro-workspace
clawhub install self-improving-agent --workdir /Users/minicat/.openclaw/xiaomi-workspace
```

### find-skills

Lets the agent search ClawHub for relevant skills when it encounters something it can't do. Only installed for minicat — 凌若 and 小蜜 don't need it.

```bash
cd /Users/minicat/.openclaw/workspace
clawhub install find-skills
```

Both skills have minimal daily token overhead — only a short description string stays in context for trigger matching. The full SKILL.md content only loads when activated.
