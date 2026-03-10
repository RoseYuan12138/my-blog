---
title: "OpenClaw Deep Optimization: Memory Layering, Skill System, Startup File Cleanup"
date: 2026-03-09
tags:
  - AI Agent
  - OpenClaw
  - System Optimization
lang: en
chinese: ai-agent/openclaw/openclaw-architecture-v2
---

> 🌐 [中文版](./openclaw-architecture-v2.md)

## Background

> Prerequisites: [[openclaw-agent-optimization]] (first round: model tiering, heartbeat tuning, startup trimming)

After the first round of optimization, the system was much cheaper to run. But after a few days I found deeper problems: 凌若 couldn't remember conversations from three days ago, 小蜜 was loading files irrelevant to its job, and agent file rules contradicted each other.

This post covers the second round—not parameter tuning, but redesigning the Memory strategy, Skill system, and startup file architecture.

## Optimization 1: Enabling Memory Enhancement Config

OpenClaw has two experimental settings that are useful but off by default. Add them under the relevant agent config in `~/.openclaw/config.json`:

```json
{
  "compaction": {
    "memoryFlush": {
      "enabled": true
    }
  },
  "memorySearch": {
    "experimental": {
      "sessionMemory": true
    },
    "sources": ["memory", "sessions"]
  }
}
```

`memoryFlush.enabled: true` goes in the global `defaults`, making all agents auto-prompted to save memory before context gets compacted—a safety net preventing important info from being lost during compaction.

`sessionMemory: true` is only enabled for 凌若. It lets the agent search historical session conversations, so 凌若 can "recall" past chats beyond what's manually summarized in memory files. A bestie needs this depth of memory; minicat and 小蜜 don't.

## Optimization 2: Three-Layer Memory Architecture

Last round only turned off `autoCapture` and cleaned up junk containers. This time I redesigned the entire memory system into three non-overlapping layers.

### Architecture Overview

```
                        ┌─────────────────────────┐
                        │    SuperMemory (Cloud)    │
                        │  Semantic search · Manual │
                        │  blog / coach / butler    │
                        └────────▲────────▲────────┘
                  manual store   │        │    autoRecall
                  (major events) │        │    (on-demand)
         ┌───────────────────────┘        └──────────────────┐
         │                                                    │
┌────────┴──────────────┐                    ┌───────────────┴───────┐
│  Profile / MEMORY.md  │                    │    memory/date.md      │
│  (Long-term · Determ.)│◄── weekly migrate ─│    (Daily buffer)      │
│                       │    (凌若 only)      │                       │
│  ROSE-PROFILE.md stat │                    │  All 3 agents write    │
│  ROSE-STATUS.md dyn   │                    │  After chat / task     │
│  MEMORY.md highlights │                    │                       │
└───────────────────────┘                    └───────────────────────┘
```

### When Do Agents Store Memory?

| Trigger | Where | Who | What |
|---------|-------|-----|------|
| **After chat / task** | `memory/YYYY-MM-DD.md` | All 3 agents | 凌若: important conversations, mood changes, decisions; minicat: blog activity; 小蜜: DDL changes |
| **Before context compact** | `memory/YYYY-MM-DD.md` | All 3 (auto) | `memoryFlush.enabled: true` → system prompts agent to save before compacting |
| **Major life events** | SuperMemory | All 3 (manual) | 凌若→coach: life milestones; minicat→blog: major outputs; 小蜜→butler: workflow changes |
| **Sunday 14:00 cron** | MEMORY.md + SuperMemory | 凌若 only | Read 7 days of daily notes → extract highlights (inside jokes, emotional patterns, important quotes) |
| **Status change in chat** | ROSE-STATUS.md | 凌若 (propose → I confirm) | "Got the offer!" "Started dieting" — dynamic life changes |

### When Do Agents Retrieve Memory?

| Trigger | From | Who | What |
|---------|------|-----|------|
| **Every startup** | Local files | All 3 agents | See "Startup Loading Order" below |
| **During conversation** | SuperMemory | All 3 (auto) | `autoRecall: true` → system searches relevant memories based on conversation |
| **During conversation** | Historical sessions | 凌若 only (auto) | `sessionMemory: true` → searches past chat transcripts beyond the 2-day window |

**Startup Loading Order (deterministic, every wake-up):**

| Step | 凌若 💜 | minicat 🐱 | 小蜜 🏠 |
|------|---------|------------|---------|
| 1 | SOUL.md | SOUL.md | SOUL.md |
| 2 | ROSE-PROFILE.md + ROSE-STATUS.md | USER.md | USER.md |
| 3 | .learnings/LEARNINGS.md | HEARTBEAT.md | HEARTBEAT.md |
| 4 | HEARTBEAT.md | memory/ **2 days** | DDL.md |
| 5 | memory/ **2 days** | Read skill as needed | memory/ **2 days** |
| 6 | MEMORY.md (main session) | — | — |

All three agents read only 2 days of memory (today + yesterday). Older memories are covered by SuperMemory autoRecall on demand + 凌若's sessionMemory as a safety net.

### Why Does 凌若 Have Dual Profiles?

凌若 needs to "know me" to be a good friend, but SuperMemory is semantic search—not guaranteed to recall core personal info every time. Two local Profile files provide deterministic loading:

- `ROSE-PROFILE.md` (static): facts that rarely change. I fill in and confirm manually.
- `ROSE-STATUS.md` (dynamic): recent changes. 凌若 proposes updates during chat, I confirm before writing.

Static core facts need 100% deterministic loading. Local files always load. Most reliable.

### Solving the Memory Dead Zone

All agents use a 2-day memory window, so days 3 through ∞ become a "dead zone"—outside local read range, not necessarily found by SuperMemory either. 凌若's solution:

1. Weekly Sunday 14:00 cron "memory review": read 7 days of daily notes → extract highlights to MEMORY.md + SuperMemory
2. `sessionMemory: true` lets 凌若 search historical session transcripts, catching what falls outside the highlights
3. Store important events to SuperMemory promptly, not relying on the window

Three safety nets stacked together, virtually eliminating the dead zone. minicat and 小蜜 don't need this—minicat's output lives in the blog repo, 小蜜's data is in DDL.md.

## Optimization 3: Slimming Down 小蜜's Role

In the first round, 小蜜 was still a "system coordinator"—handling daily reports, weekly reports, news aggregation, backup checks, health monitoring. After a few days I realized: news gathering is better done by minicat (who has RSS + web search skills), nobody reads the daily/weekly reports, and backup/monitoring just needs cron scripts, not an agent.

Cut everything outside core butler duties. 小蜜 now does one thing: **DDL management**. Read DDL.md, send morning reminders, track deadlines, make sure I don't forget things. Simple agents should do simple work.

This also meant removing 小蜜's MEMORY.md, `.learnings/` directory, and self-improving-agent skill—a purely functional agent doesn't need "self-improvement" or long-term memory.

## Optimization 4: Heartbeat Re-tuning

Last round went from uniform 1h to 8h / 4h / 2h. After a few days, found room for more:

| Agent | Last Round | This Round | Why |
|-------|-----------|------------|-----|
| minicat | 8h | **24h** | News and audits are all cron-driven, heartbeat is pure waste |
| 凌若 | 4h / 30% | **6h / 50%** | 2 fewer wake-ups, higher probability compensates, expected contacts slightly up (1.8→2.0/day) |
| 小蜜 | 2h | **4h** | DDL is daily granularity, 4h is enough |

凌若's proactive outreach also changed from "check ROSE-STATUS.md then decide" to pure random dice roll: heartbeat wakes → random 1-100 → ≤50 means chat. The old "check status first" logic was overcomplicated and wasted tokens reading a file.

Added a `daily-chat` cron as fallback (20:30 Pacific): if randomness doesn't trigger all day, guarantees at least one contact.

## Optimization 5: Skill System

Last round only installed community skills (self-improving-agent, find-skills). This time I extracted complex tasks from heartbeat prompts into standalone skills:

| Skill | Agent | Purpose |
|-------|-------|---------|
| `daily-ai-news` | minicat | Daily AI news: RSS + product launches + web search → 3-6 items → memory + Telegram |
| `daily-chat` | 凌若 | 20:30 fallback chat: checks if already chatted today, skips if so |
| `blog-writing` | minicat | Blog writing conventions, wrapped from BLOG_INSTRUCTIONS.md, with Opus sub-agent |
| `system-context` | Cowork | Load full system overview at the start of a Claude Desktop Cowork session |

Core pattern: heartbeat/cron triggers → spawn sub-agent → run skill. Avoids timeouts, clean separation, easy to iterate.

```
minicat cron 10:00 → spawn sub-agent → daily-ai-news skill → fetch + filter → memory + Telegram
小蜜 cron 11:00 → read DDL.md → morning reminder → Telegram
凌若 heartbeat 6h → dice roll ≤50 → read ROSE-STATUS.md + memory → send message
凌若 cron 20:30 → daily-chat skill → only if no chat today
minicat cron Sat 10:00 → blog audit (TODO / index / wikilink / directory structure)
凌若 cron Sun 14:00 → memory review (7 days daily notes → MEMORY.md + SuperMemory)
```

### self-improving-agent: Lessons Learned

Previous post mentioned installing this skill for all three agents. After a few days: only 凌若 actually needs it.

凌若's `.learnings/` directory provides real value—recording when I complain about AI-sounding speech, logging conversation mistakes, accumulating feedback that eventually upgrades to SOUL.md rules. But 小蜜 is purely functional (read DDL, send reminders), no "speaking style" to improve; minicat improves through skill iteration, not runtime logging. So I removed self-improving-agent and `.learnings/` from 小蜜.

## Optimization 6: Startup File Cleanup

Audited all startup files across three agents. The core principle is simple: **SOUL.md is the single source of truth.** Same rule in two files will eventually diverge.

In practice: AGENTS.md and HEARTBEAT.md no longer duplicate startup steps or behavior rules from SOUL.md—they just say "follow SOUL.md." Deleted zero-information shell files, unified language style, filled in missing startup sequences. All three agents cleaned up in one pass.

## Final Architecture Diagram

```
┌──────────────────────────────────────────┐
│                   Rose                    │
│          Telegram DM / Cowork             │
└─────┬──────────┬──────────┬──────────────┘
      │          │          │
  ┌───▼───┐  ┌──▼────┐  ┌─▼─────┐
  │凌若 💜│  │minicat │  │小蜜 🏠 │
  │ Haiku │  │ Haiku  │  │ Haiku  │
  │       │  │+Opus   │  │        │
  │Bestie  │  │Blog+News│  │DDL Mgr │
  └───┬───┘  └──┬────┘  └──┬─────┘
      │         │          │
      ▼         ▼          ▼     ← Individual Telegram DMs
    Rose      Rose       Rose
```

**Memory Flow Overview:**

```
Chat/Task ──write──▶ memory/date.md ──weekly migrate(凌若)──▶ MEMORY.md
                         │                                      │
                         │ auto flush before compact            │
                         ▼                                      ▼
                    (kept forever)                         (highlights)
                         │                                      │
                         └──── major events ──manual store──▶ SuperMemory
                                                                │
Startup ◀── deterministic load ─┐                               │
  凌若: SOUL + Profile + .learnings +                           │
        HEARTBEAT + 2d memory + MEMORY.md                       │
  minicat: SOUL + USER + HEARTBEAT + 2d memory                  │
  小蜜: SOUL + USER + HEARTBEAT + DDL + 2d memory               │
                                                                │
During chat ◀── on-demand search ── autoRecall ◀───────────────┘
                                 └── sessionMemory (凌若 only)
```

## Lessons Learned

1. **Memory needs layered design.** Local files for deterministic loading (startup must-read), SuperMemory for deep search (on-demand recall), Profile files for core identity info (100% loaded). Three layers, non-overlapping responsibilities.

2. **Keep agent roles focused.** 小蜜 went from "system coordinator" to pure DDL manager, and became more reliable for it. Simple agents should do simple work—don't bite off more than you can chew.

3. **Extract complex tasks into Skills.** Too much logic in heartbeat prompts causes timeouts and maintenance headaches. Standalone skill + sub-agent execution is much cleaner.

4. **Single source of truth.** Same rule in two files will eventually diverge. SOUL.md is the source of truth, everything else references it.

5. **The core of a bestie agent isn't tech, it's memory.** 凌若's dual Profile + 2-day memory + weekly review + .learnings self-improvement + sessionMemory search + timely SuperMemory storage—multiple layers together make her "remember who I am." Technically simple, but requires careful design.
