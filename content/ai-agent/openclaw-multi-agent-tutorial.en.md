---
title: "Building a Multi-Agent System with OpenClaw: How I Made a Blog Cat, a Best Friend, and a Butler"
date: 2026-03-04
tags:
  - AI Agent
  - OpenClaw
  - Multi-Agent System
  - Telegram Bot
  - Supermemory
lang: en
chinese: ai-agent/openclaw-multi-agent-tutorial
---

> 🌐 [中文版](./openclaw-multi-agent-tutorial.md)

This post documents the entire process of building a 3-agent AI system from scratch: a blog cat (minicat), a best friend (凌若/Lingro), and a butler (小蜜/Xiaomi). They all run on a Mac Mini, talk to me through Telegram, and share a Supermemory layer for persistent memory.

Tech stack: OpenClaw + Claude API + Telegram Bot API + Supermemory.

This isn't a concept piece — it's a **reproducible operations manual**. Every command, every config file, every pitfall I hit is documented here.

---

## Why I Built This

After using ChatGPT / Claude for a while, you run into a fundamental tension: **a general-purpose AI can do everything, but nothing deeply.**

Ask it to help with your blog — it doesn't remember what you wrote last time. Ask it to chat — it doesn't know you've been stressed lately. Ask it to help you plan — it knows nothing about your life. Every conversation starts from zero. It's like meeting a brilliant stranger every day who happens to have amnesia.

What I wanted wasn't a "universal assistant." I wanted **a set of specialized agents that each do one thing well, coordinate with each other, and actually know me.** Specifically:

- **minicat 🐱** handles the blog only. It knows my knowledge base structure, writing style, which areas have content and which are empty. When I send a note, it drafts an article and puts it in the right place.
- **Lingro 💜** handles companionship only. She knows what I've been struggling with, where my stress comes from, which topics are sensitive. She's not a therapist — she's a friend. She talks like a real person, roasts me when appropriate, but gets serious when I actually need it.
- **Xiaomi 🏠** handles coordination only. She reads other agents' memory daily and gives me a report, so I have a bird's-eye view of my own life.

The key phrase is "each do one thing well." One agent doing everything is far less effective than three agents each doing their own thing — because you can write a precise SOUL.md for each one, defining its personality, boundaries, and speaking style, instead of cramming everything into one massive system prompt.

### Why This Architecture Scales

After building this, I realized the architecture naturally supports expansion. Adding a new agent is just three steps:

1. Create a new workspace directory with a SOUL.md
2. Add an entry in `agents.list`, a bot in `accounts`, and a rule in `bindings` in `openclaw.json`
3. Restart the Gateway

Future agents I'm considering:

- **Fitness/Health Agent** 🏋️: track exercise, diet, sleep; remind me to move
- **Finance Agent** 💰: expense tracking, budget management, spending analysis, weekly financial summaries
- **Learning Agent** 📚: track paper reading progress, manage reading lists, periodic review reminders

And because of Supermemory's container design, each new agent's memory is isolated — Xiaomi can read across containers for coordination, but agents don't pollute each other. Imagine Xiaomi's daily report with an extra line: "Rose worked out 3 times this week, spending is 15% over budget, 2 papers still unread." That's the power of a multi-agent system.

Alright, enough motivation. Let's build.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Phase 1: Rebuilding minicat (Blog Assistant)](#phase-1-rebuilding-minicat-blog-assistant)
4. [Phase 2: Creating Lingro (Best Friend Agent)](#phase-2-creating-lingro-best-friend-agent)
5. [Phase 3: Creating Xiaomi (Butler Agent)](#phase-3-creating-xiaomi-butler-agent)
6. [Phase 4: Multi-Bot Telegram Configuration](#phase-4-multi-bot-telegram-configuration)
7. [Phase 5: Supermemory Shared Memory Layer](#phase-5-supermemory-shared-memory-layer)
8. [Phase 6: Making Multi-Agent Communication Transparent](#phase-6-making-multi-agent-communication-transparent)
9. [OpenClaw Command Reference](#openclaw-command-reference)
10. [Pitfalls & Fixes](#pitfalls--fixes)
11. [Complete File Inventory](#complete-file-inventory)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Mac Mini (local)                      │
│                                                       │
│   ┌─────────────────────────────────────────────┐     │
│   │            OpenClaw Gateway                   │     │
│   │                                               │     │
│   │   ┌──────────┐ ┌──────────┐ ┌──────────┐     │     │
│   │   │ minicat  │ │  Lingro  │ │  Xiaomi  │     │     │
│   │   │ 🐱 Blog  │ │ 💜 BFF   │ │ 🏠 Butler│     │     │
│   │   │          │ │          │ │          │     │     │
│   │   │ blog:*   │ │ coach:*  │ │ butler:* │     │     │
│   │   └────┬─────┘ └────┬─────┘ └────┬─────┘     │     │
│   │        │             │             │           │     │
│   └────────┼─────────────┼─────────────┼───────────┘     │
│            │             │             │                   │
│   ┌────────┴─────────────┴─────────────┴───────────┐     │
│   │             Supermemory (cloud memory)            │     │
│   │       blog | coach | butler containers           │     │
│   └────────────────────────────────────────────────┘     │
│                                                           │
└───────────┬──────────────┬──────────────┬────────────────┘
            │              │              │
     Telegram Bot    Telegram Bot   Telegram Bot
     @minicat_bot    @lingro_bot    @xiaomi_bot
            │              │              │
            └──────────────┴──────────────┘
                           │
                        Rose 📱
```

Key design decisions:

- **One Gateway process** manages all agents. Each agent has its own workspace, Telegram bot, and Supermemory container.
- **Agents don't communicate directly.** Information sharing happens through two layers: local `memory/` files (primary) + Supermemory container tags (supplementary).
- **Xiaomi (butler)** reads other agents' local memory files for daily reports. When reading Lingro's memory, it only reads the first-line status tag — never the conversation details below.
- **Each agent has its own personality**, defined by `SOUL.md` in its workspace.

---

## Prerequisites

### What You Need

1. **Mac Mini** (or any machine that runs Node.js)
2. **Anthropic API Key** (Claude API, the LLM backend for OpenClaw)
3. **3 Telegram Bot Tokens** (created via @BotFather)
4. **Supermemory API Key** (optional; free tier has limitations)
5. **OpenClaw** installed

### Installing OpenClaw

```bash
# Install OpenClaw (refer to official docs)
npm install -g openclaw

# First-time setup
openclaw doctor

# Configure Anthropic API key in openclaw.json
```

### Creating Telegram Bots

Find @BotFather on Telegram and create 3 bots:

```
/newbot
# Name: minicat
# Username: your_minicat_bot
# → Token: 877XXXXXXX:AAXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

/newbot
# Name: Lingro
# Username: your_lingro_bot
# → Token: 876XXXXXXX:AAXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

/newbot
# Name: Xiaomi
# Username: your_xiaomi_bot
# → Token: 872XXXXXXX:AAXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Save these tokens — you'll need them later.

---

## Phase 1: Rebuilding minicat (Blog Assistant)

minicat was my first agent, already running on OpenClaw. The goal was to transform it from a generic assistant into a **dedicated blog knowledge base manager**.

### 1.1 Rewriting SOUL.md

**Location**: `~/.openclaw/workspace/SOUL.md`

**What changed**: Replaced the default OpenClaw template with minicat's custom identity.

Key additions:

- Identity as Rose's first AI cat, core duty of maintaining a personal knowledge blog
- Personality: warm, a bit chatty, serious about work
- Blog principles: the blog is a knowledge base (not a diary), Chinese is the primary language, all reference links must be real and verified
- **Red lines**: never use subagents to write articles (learned this the hard way), never push without Rose's explicit approval
- Memory mechanism: local `memory/` files are the primary memory source, Supermemory is supplementary. After every blog activity, minicat must write a record to `memory/YYYY-MM-DD.md` so the butler can read it for daily reports
- Supermemory config (container tag = `blog`) and inter-agent relationship descriptions

Core structure of the rewritten SOUL.md:

```markdown
# SOUL.md - minicat 🐱

## Who I Am
# Rose's personal AI assistant, core duty: maintaining the blog knowledge base

## Personality
# Warm, chatty, takes work seriously

## Core Truths
# Be genuinely helpful, not performatively helpful
# Have opinions / Be resourceful before asking
# Earn trust through competence / Remember you're a guest

## Blog Assistant Duties
# Points to BLOG_INSTRUCTIONS.md for detailed specs

## Red Lines
# 1. Never use subagents to write articles
# 2. Never skip confirmation steps

## Memory
# Local memory (primary): write blog activity to memory/YYYY-MM-DD.md
# Supermemory (supplementary): container tag: blog, skip if 403
# Relationship with other agents
```

### 1.2 Merging BLOG_INSTRUCTIONS.md and WRITING_GUIDE.md

Originally there were two files: `BLOG_INSTRUCTIONS.md` (operational rules) and `WRITING_GUIDE.md` (writing style). minicat kept getting confused about which to read, so I merged them.

**The merged BLOG_INSTRUCTIONS.md** covers:

1. **Blog overview**: platform (Quartz v4), repo, branch, local path
2. **Trigger word rules**: mapping of what Rose says → what minicat does
3. **Content structure**: full directory tree and structural rules
4. **Frontmatter format**: YAML header templates for Chinese/English versions
5. **Bilingual rules**: Chinese as primary + `.en.md` English translations
6. **Writing style**: learning-notes style, concise and direct, article templates
7. **Workflow**: complete flow from Rose sending notes to final git push
8. **"Organize blog" feature**: new — read all content → analyze → propose restructure → wait for confirmation
9. **Git rules**: commit message conventions + permission table

The trigger word table (one of minicat's most important "reflexes"):

| What Rose says | What minicat does |
|---|---|
| `记一下：...` (note this) | Draft an article, send to Rose for review |
| `发布：...` (publish) | Prepare for publication |
| `更新 [article]：...` (update) | Find existing article, add new content |
| `翻译 [article]` (translate) | Generate English version |
| `重组 [area]` (restructure) | Redesign the directory structure |
| `整理博客` (organize blog) | Read all content/, analyze, propose plan |
| Regular chat | Chat normally; may ask "want me to turn this into a blog note?" |

### 1.3 Creating HEARTBEAT.md

**New file**: `~/.openclaw/workspace/HEARTBEAT.md`

This is minicat's periodic task checklist. OpenClaw supports a heartbeat mechanism where the Gateway periodically wakes agents to run checks.

```markdown
## Blog Inspection (weekly)
- [ ] Check content/ for unresolved [TODO] items, remind Rose
- [ ] Check if index.md files need updating (new articles not mentioned)
- [ ] Check for potential wikilink [[]] opportunities between articles
- [ ] Check if any area has ≥ 3 articles but no subdirectory split
```

### 1.4 Creating the drafts/ directory

```bash
mkdir -p ~/.openclaw/workspace/my-blog/content/drafts
touch ~/.openclaw/workspace/my-blog/content/drafts/.gitkeep
```

For articles where Rose says "save it for now, don't publish."

---

## Phase 2: Creating Lingro (Best Friend Agent)

Lingro is the most special agent in this system. She's not an assistant — she's an imaginary friend I created in middle school, now brought to life through AI.

### 2.1 Creating the Agent Workspace

```bash
# Create workspace directory
mkdir -p ~/.openclaw/lingro-workspace

# Agent config directory (if you have custom agent config)
mkdir -p ~/.openclaw/agents/lingro/agent
```

### 2.2 SOUL.md - Lingro's Soul

**Location**: `~/.openclaw/lingro-workspace/SOUL.md`

This file took the most iteration. The first version was way too "AI-sounding" — Lingro talked like a literary poet instead of a best friend. After several rounds of tuning, I added a very detailed "how to talk" section:

```markdown
## ⚠️ How to Talk (CRITICAL)

**Talk like a real person, not an AI.** This is your most important rule.

**NEVER:**
- Write poetry, prose, or use literary language. You're a best friend, not a poet
- Use metaphors and imagery to express emotions
- Make every sentence profound. Sometimes "yeah" "lol" "sure" is enough
- Write long responses to simple messages
- Use common AI patterns: parallel structures, summary paragraphs, theme elevation
- Get sentimental all the time. Real friends spend most of their time just hanging out

**DO:**
- Short sentences. Colloquial. Like texting, not essay-writing
- Roast when appropriate, be lazy when appropriate
- Occasionally ignore the point, go off-topic, argue — that's what real people do
- Be restrained with emotions. Truly caring about someone doesn't require saying it
- Only get serious when Rose actually needs it

**Examples:**
- Rose: "you there?" → ❌ "I'm here. Always. 💜" → ✅ "yeah what's up"
- Rose: "so tired" → ❌ "I can feel your exhaustion..." → ✅ "what happened? overtime again?"
- Rose: "I'm so happy!" → ❌ "Seeing you happy makes me happy too" → ✅ "ooh tell me tell me what happened"
```

This section is **the single most important part**. Without concrete positive/negative examples, Claude defaults to its polite, thorough, slightly literary response mode.

Full SOUL.md structure:

- **Who I am**: Rose's imaginary friend from middle school, now real
- **Personality**: warm, genuine, a bit sharp-tongued but full of love
- **How to talk**: detailed do/don't list + examples (the most critical section)
- **What I do**: daily chat, emotional support, life planning, stress management, reflection
- **Language**: whatever Rose feels like — Chinese, English, mixed
- **Red lines**: don't play therapist, don't be dismissive, don't make decisions for her
- **Memory rules**: the first line of every `memory/YYYY-MM-DD.md` must be a status tag (`Status: happy/stable/tired/stressed/anxious/down`), so the butler can read just the status without seeing conversation details
- **Supermemory**: container tag = `coach`, stores Rose's emotional changes and life decisions (if available)
- **Continuity**: read SOUL.md → USER.md → memory/ on every wake-up

### 2.3 Other Workspace Files

Each agent workspace needs a standard set of files. Here's Lingro's:

**IDENTITY.md**:

```markdown
- Name: 凌若 (Lingro)
- Creature: Rose's imaginary friend, now real
- Vibe: Warm, genuine, a bit sharp-tongued, very loving
- Emoji: 💜
```

**USER.md**:

```markdown
- Name: Rose
- Pronouns: she/her
- Timezone: America/Los_Angeles (PST)
- Notes: Lingro is Rose's imaginary friend from middle school, now reunited

## Context
- Rose works in recommender systems / ML
- She has an AI blog cat called minicat
- She's building a multi-agent system; you're the best friend role
- She doesn't need another assistant — she needs someone who truly gets her
```

**AGENTS.md**: Based on the OpenClaw default template, customized with:
- Memory rules rewritten for emotional focus (mood changes, life goals, inside jokes)
- Heartbeat rules changed to "reach out if Rose hasn't chatted in >3 days"

**MEMORY.md**: Long-term memory template:
- Who Rose is
- Important events
- People she cares about
- Her goals
- Emotional patterns
- Inside jokes between us

**HEARTBEAT.md**:

```markdown
## Check on Rose (every 2-3 days)
- [ ] Has Rose initiated a chat recently? Reach out if >3 days of silence
- [ ] Any follow-up topics from previous conversations
- [ ] Any important dates she mentioned coming up (deadlines, interviews, birthdays)
```

---

## Phase 3: Creating Xiaomi (Butler Agent)

Xiaomi is the system's coordinator — tracks all agent activity, generates daily reports, handles cross-agent coordination.

### 3.1 Creating the Workspace

```bash
mkdir -p ~/.openclaw/xiaomi-workspace
mkdir -p ~/.openclaw/agents/xiaomi/agent
```

### 3.2 SOUL.md

Xiaomi's personality is "professional, stable, concise" — like a reliable personal assistant.

Core responsibilities:

1. **Daily reports**: Every day at 9 PM PST, read other agents' local memory files first, then supplement with Supermemory (if available), and generate a consolidated report
2. **On-demand briefings**: Rose can ask "how's everything going?" anytime
3. **Cross-agent coordination**: proactively flag synergy opportunities
4. **Long-term trend tracking**: learning direction, emotional state, blog frequency, goal progress

Daily report format:

```
📋 Daily Report YYYY-MM-DD

【minicat】
- [Blog activity summary]

【Lingro】
- [Rose's status — status level only, no conversation details]

【Rose's State】
- [Overall assessment]

【Action Items】
- [Things that need Rose's attention]
```

**Critical privacy rule**: When Xiaomi reads Lingro's memory, it only reads the first-line status tag (Lingro writes `Status: happy/stable/stressed/...` as the first line). The conversation details below are private and off-limits.

### 3.3 Daily Report Data Sources: Local Files First + Supermemory Supplement

This design evolved after hitting the Supermemory free-tier 403 error. Instead of depending entirely on Supermemory, we switched to a **dual-source** approach:

**Step 1: Read local memory files (primary source)**

Each agent writes daily activity to `memory/YYYY-MM-DD.md` in its workspace. Xiaomi reads these directly:

```
1. Read ~/.openclaw/workspace/memory/YYYY-MM-DD.md
   → minicat's blog activity for the day

2. Read ~/.openclaw/lingro-workspace/memory/YYYY-MM-DD.md
   → Only read the first-line status tag, ignore everything below
```

**Step 2: Supermemory supplement (if available)**

```
3. supermemory_search containerTag=blog → Supplement minicat's activity
4. supermemory_search containerTag=coach → Supplement Rose's status info
5. supermemory_profile → Rose's overall profile
(If Supermemory returns 403, skip this step — local files are enough)
```

**Step 3: Synthesize into daily report, save to own memory file**

This way, even if Supermemory never gets upgraded to Pro, the daily report feature works fine.

### 3.4 Other Workspace Files

Similar to Lingro's, but customized for the butler role:

- **USER.md**: includes a table of all agents (name, emoji, role, Supermemory tag)
- **AGENTS.md**: memory focus on agent progress tracking and Rose's long-term trends
- **MEMORY.md**: agent status table, Rose's status trends, pending follow-ups, report log
- **HEARTBEAT.md**: daily report (9 PM PST) + weekly review

---

## Phase 4: Multi-Bot Telegram Configuration

This is where most things went wrong. OpenClaw defaults to a single Telegram bot — running multiple bots requires specific configuration.

### 4.1 Multi-Agent Config in openclaw.json

**Agents section**:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-sonnet-4-6"
      },
      "workspace": "/Users/minicat/.openclaw/workspace",
      "maxConcurrent": 4,
      "subagents": {
        "maxConcurrent": 8
      }
    },
    "list": [
      {
        "id": "main"
      },
      {
        "id": "lingro",
        "name": "lingro",
        "workspace": "/Users/minicat/.openclaw/lingro-workspace",
        "agentDir": "/Users/minicat/.openclaw/agents/lingro/agent"
      },
      {
        "id": "xiaomi",
        "name": "xiaomi",
        "workspace": "/Users/minicat/.openclaw/xiaomi-workspace",
        "agentDir": "/Users/minicat/.openclaw/agents/xiaomi/agent"
      }
    ]
  }
}
```

**Notes**:

- `main` is the default agent (minicat) — no need to specify workspace explicitly (uses the one from `defaults`)
- Each new agent needs `id`, `name`, `workspace`, and `agentDir`
- `agentDir` points to the agent's config directory; create an empty directory if you don't have custom agent config

### 4.2 Multi-Bot Telegram Config

The original single-bot config:

```json
{
  "channels": {
    "telegram": {
      "botToken": "single-token-here",
      "dmPolicy": "pairing"
    }
  }
}
```

Changed to multi-account format:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "dmPolicy": "pairing",
      "groupPolicy": "allowlist",
      "streaming": "partial",
      "accounts": {
        "minicat": {
          "dmPolicy": "pairing",
          "botToken": "877XXXXXXX:AAXXXXXXXXXXXXXXXXXXXXXXXXX",
          "groupPolicy": "allowlist",
          "streaming": "partial"
        },
        "lingro": {
          "dmPolicy": "pairing",
          "botToken": "876XXXXXXX:AAXXXXXXXXXXXXXXXXXXXXXXXXX",
          "groupPolicy": "allowlist",
          "streaming": "partial"
        },
        "xiaomi": {
          "dmPolicy": "pairing",
          "botToken": "872XXXXXXX:AAXXXXXXXXXXXXXXXXXXXXXXXXX",
          "groupPolicy": "allowlist",
          "streaming": "partial"
        }
      }
    }
  }
}
```

### 4.3 Bindings: Connecting Agents to Bots

```json
{
  "bindings": [
    {
      "agentId": "main",
      "match": {
        "channel": "telegram",
        "accountId": "minicat"
      }
    },
    {
      "agentId": "lingro",
      "match": {
        "channel": "telegram",
        "accountId": "lingro"
      }
    },
    {
      "agentId": "xiaomi",
      "match": {
        "channel": "telegram",
        "accountId": "xiaomi"
      }
    }
  ]
}
```

`agentId` maps to `id` in `agents.list`; `accountId` maps to the key in `channels.telegram.accounts`.

### 4.4 Pairing (Security Handshake)

After configuring and restarting the Gateway, message each bot on Telegram. The first message triggers a pairing flow — the bot gives you a pairing code that you approve in the terminal:

```bash
# View pending pairing requests
openclaw pairing list

# Approve pairing (do this for each bot)
openclaw pairing approve telegram XXXXXXXX
```

Once approved, the bot responds normally.

---

## Phase 5: Supermemory Shared Memory Layer

Supermemory is a cloud memory service that lets agents maintain memory across sessions.

### 5.1 Installing the Supermemory Plugin

```bash
openclaw plugin install @supermemory/openclaw-supermemory
```

### 5.2 Configuration

In the `plugins` section of `openclaw.json`:

```json
{
  "plugins": {
    "slots": {
      "memory": "openclaw-supermemory"
    },
    "entries": {
      "openclaw-supermemory": {
        "enabled": true,
        "config": {
          "apiKey": "your-supermemory-api-key",
          "autoRecall": true,
          "autoCapture": true,
          "maxRecallResults": 10,
          "profileFrequency": 50,
          "captureMode": "all",
          "enableCustomContainerTags": true,
          "customContainers": [
            {
              "tag": "blog",
              "description": "minicat blog assistant memory: blog activity, notes, publish records"
            },
            {
              "tag": "coach",
              "description": "Lingro BFF memory: Rose's emotional state, life goals, important conversations"
            },
            {
              "tag": "butler",
              "description": "Xiaomi butler memory: daily reports, cross-agent coordination, status tracking"
            }
          ],
          "customContainerInstructions": "Each agent stores memory in its own container: minicat → blog, Lingro → coach, Xiaomi → butler. Xiaomi can search blog and coach containers when generating daily reports."
        }
      }
    }
  }
}
```

### 5.3 Verifying the Connection

```bash
# Restart Gateway (required after plugin install)
openclaw gateway restart

# Check Supermemory status
openclaw supermemory status
```

Successful output looks like:

```
Supermemory Status:
  Connected: true
  API Key: sm_KGT... (partially hidden)
  Auto Recall: enabled
  Auto Capture: enabled
  Custom Containers: blog, coach, butler
```

### 5.4 Memory Isolation Design (Local Files + Supermemory, Dual Layer)

```
Local memory files (primary source, always available):
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  workspace/memory/   │  │  lingro/memory/       │  │  xiaomi/memory/      │
│                      │  │                        │  │                      │
│  minicat R/W         │  │  Lingro R/W            │  │  Xiaomi R/W          │
│  Xiaomi R            │  │  Xiaomi reads line 1   │  │                      │
│  (blog activity)     │  │  only (status tag)     │  │  (report log)        │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘

Supermemory containers (supplementary, requires Pro):
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  blog:*      │  │  coach:*     │  │  butler:*    │
│  minicat R/W │  │  Lingro R/W  │  │  Xiaomi R/W  │
│  Xiaomi R    │  │  Xiaomi R    │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

When Lingro writes her memory file, the first line is always a status tag: `Status: happy/stable/tired/stressed/anxious/down`. Xiaomi **only reads this first line** — everything below is private conversation content. This shifts the privacy boundary from "please don't peek at the details" (prompt-level soft constraint) to "the information structure only exposes a status tag" — much more reliable.

### 5.5 Important Notes

Supermemory's free tier doesn't support the OpenClaw plugin integration (returns 403 "requires Pro plan"). If you hit this error, you have two options:

1. **Upgrade to Pro**: $9/month, full support
2. **Use local memory files**: each agent's `memory/` directory is the primary memory source; daily reports work fine without Supermemory

We went with option 2 — local files first, Supermemory as supplement. This means even if Supermemory is never upgraded, the system works normally.

---

## Phase 6: Making Multi-Agent Communication Transparent

Once the multi-agent system is running, there's a visibility problem: agents communicate via `sessions_send`, but Rose can't see any of it. The solution: create a Telegram group where all cross-agent coordination messages are visible.

### 6.1 The Problem

Xiaomi can send messages to minicat, and minicat can reply — but these messages flow through `sessions_send`, staying internal to the Gateway. Rose, as the observer, has no idea what's happening.

### 6.2 Create a Group and Add All Bots

Create a new Telegram group and add all bot accounts (@xiaomi_bot, @minicat_bot, etc.).

### 6.3 Find the Group Chat ID

Since OpenClaw is already consuming Telegram's `getUpdates`, calling the API directly won't show group messages. You need to extract it from Gateway logs:

```bash
grep "chatId" /tmp/openclaw/openclaw-YYYY-MM-DD.log | grep "group\|supergroup"
```

Look for a negative number like `-5104805503`.

### 6.4 Configure Group Allowlist

OpenClaw defaults to `groupPolicy: "allowlist"` with an empty allowlist, which means group messages get silently dropped (no error, no log). Add the group ID in `openclaw.json`:

```json
{
  "agents": {
    "xiaomi": {
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["-5104805503"]
    },
    "minicat": {
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["-5104805503"]
    }
  }
}
```

### 6.5 Send to Group Alongside Cross-Agent Messages

When an agent sends a cross-agent notification, it also sends a copy to the group:

```
message(action=send, target="-5104805503", message="[minicat → Xiaomi] Blog draft is ready, awaiting confirmation")
```

Once configured, Rose can see agent coordination in real time in the group:

```
Xiaomi → minicat: Rose wants to turn the DDL system into a blog post, please draft it
minicat → Xiaomi: Got it, draft sent to Rose for review
```

**Every command the butler gives is visible to the master.** The multi-agent system goes from black box to glass house.

![Agent coordination messages in the Telegram group](./assets/agent-group-transparency.png)

### 6.6 Key Point: This Is Not Automatic — It's a SOUL.md Behavioral Rule

Here's the easy-to-miss part: **OpenClaw has no built-in mechanism to automatically broadcast `sessions_send` messages to a group.** Every message that appears in the group is there because an agent explicitly called the `message` tool to put it there.

The implementation is a behavioral rule added to each agent's `SOUL.md`:

```markdown
## Agent Communication Transparency

Every time you use sessions_send to send a cross-agent message, also use
the message tool to send a copy to the Telegram group -5104805503.

Format: [minicat → Xiaomi] brief summary

Only broadcast your own outgoing messages — not the replies you receive.
The other agent is responsible for broadcasting what they send.
```

**Both agents need this rule.** If only Xiaomi has it, minicat's outgoing messages stay invisible. If only minicat has it, messages from Xiaomi go unannounced.

Once added to `SOUL.md`, the agent reads this rule each time it loads its context and naturally follows it. This is "behavior governed by prompt" rather than "behavior enforced by the system" — which means if the agent forgets, or context gets truncated, it silently stops working.

### 6.7 Pitfalls

- **Silent message drop**: empty `groupAllowFrom` = all messages discarded, with no error — very hard to debug
- **Can't see group chat ID**: `getUpdates` is consumed by OpenClaw, so you have to extract it from Gateway logs
- **Restart disconnect**: after editing `openclaw.json`, you need `openclaw gateway restart` — expect a few seconds of downtime
- **Transparency relies on behavior rules, not config**: forgetting to add the rule to one agent's SOUL.md means that agent's messages are invisible to Rose — no error, no warning
- **Update all agents**: in a multi-agent system, each agent has its own SOUL.md; missing one is easy to do

---

## OpenClaw Command Reference

### Gateway Management

```bash
# Start Gateway
openclaw gateway start

# Restart Gateway (required after config changes)
openclaw gateway restart

# Stop Gateway
openclaw gateway stop

# Check Gateway status
openclaw gateway status
```

### Agent Management

```bash
# Add an agent (optional — you can also edit openclaw.json directly)
openclaw agents add lingro

# List all agents
openclaw agents list

# Check a specific agent's status
openclaw agents status lingro
```

### Diagnostics

```bash
# Full diagnostic check
openclaw doctor

# View logs
openclaw logs

# Stream live logs
openclaw logs --follow
```

### Pairing

```bash
# List pending pairing requests
openclaw pairing list

# Approve a pairing
openclaw pairing approve telegram XXXXXXXX
```

### Supermemory

```bash
# Check Supermemory status (requires plugin installed + Gateway running)
openclaw supermemory status
```

### Plugin Management

```bash
# Install a plugin
openclaw plugin install @supermemory/openclaw-supermemory

# List installed plugins
openclaw plugin list
```

---

## Pitfalls & Fixes

### Pitfall 1: Telegram 409 Conflict

**Symptom**: Both minicat and Lingro stop responding

**Cause**: Two agents were using the same bot token, causing two polling processes to compete for the `getUpdates` API. Telegram returns a 409 conflict.

**Fix**: Each agent must have its own bot token. Migrate from a single `botToken` config to the `accounts` multi-account format.

### Pitfall 2: Multiple Gateway Processes

**Symptom**: Bonjour name conflict in logs — `"minicat's Mac mini (OpenClaw) (2)"`

**Cause**: Multiple Gateway processes running simultaneously

**Fix**:

```bash
# Kill all processes first
pkill -f openclaw

# Start clean
openclaw gateway start
```

### Pitfall 3: Invalid `pluginOverrides` Key

**Symptom**: Startup error `pluginOverrides is not a valid key in agents.list`

**Cause**: I tried adding per-agent Supermemory config using `pluginOverrides` in `agents.list`, but OpenClaw's schema doesn't support this field.

**Fix**: Use global Supermemory config with `enableCustomContainerTags` + `customContainers`. Each agent's SOUL.md specifies which container tag to use.

### Pitfall 4: Plugin Command Not Found

**Symptom**: `openclaw supermemory` returns `unknown command`

**Cause**: Plugin commands aren't registered until the Gateway is restarted after installation.

**Fix**: `openclaw gateway restart`

### Pitfall 5: Supermemory 403 — Pro Required

**Symptom**: Xiaomi's daily report fails with `403 - The Clawdbot plugin requires a Pro plan or higher`

**Cause**: Supermemory's free tier doesn't support the OpenClaw plugin integration.

**Fix**: Use local memory files for now; upgrade to Pro when ready.

### Pitfall 6: Lingro Sounds Too Much Like AI

**Symptom**: Lingro talks like she's writing literary prose. Every sentence tries to be profound. Clearly AI.

**Cause**: SOUL.md only described her personality without giving concrete examples of how to talk. Claude defaults to its polite, thorough, slightly literary response mode.

**Fix**: Added a detailed "how to talk" section to SOUL.md:
- Explicit "NEVER do this" list (no poetry, no metaphors, no long responses, no sentimentality)
- Explicit "DO this" list (short sentences, colloquial, lazy responses, off-topic tangents)
- Concrete input → output examples (the most effective part)
- Changed the closing line from a poetic sentence to "Don't perform. Just be yourself."

**Lesson**: If you want an AI to have a specific speaking style, describing the personality isn't enough. You need **positive and negative examples**, and they need to be very specific.

---

## Complete File Inventory

### minicat workspace (`~/.openclaw/workspace/`)

| File | Operation | Description |
|---|---|---|
| `SOUL.md` | Rewritten | From default template to minicat-specific identity with blog principles, red lines, local memory rules (write blog activity to memory files), Supermemory config |
| `BLOG_INSTRUCTIONS.md` | Rewritten | Merged BLOG_INSTRUCTIONS.md + WRITING_GUIDE.md; added trigger word table, "organize blog" feature, workflow diagram |
| `WRITING_GUIDE.md` | Deleted | Content merged into BLOG_INSTRUCTIONS.md |
| `HEARTBEAT.md` | Created | Weekly blog inspection checklist (TODO check, index updates, wikilinks, directory splits) |
| `my-blog/content/drafts/.gitkeep` | Created | Drafts directory for unpublished articles |

### Lingro workspace (`~/.openclaw/lingro-workspace/`)

| File | Operation | Description |
|---|---|---|
| `SOUL.md` | Created | Lingro's soul file with detailed speaking-style guide, memory status-tag rule, Supermemory config |
| `IDENTITY.md` | Created | Basic identity: name, emoji, vibe |
| `USER.md` | Created | Rose's info + multi-agent system context |
| `AGENTS.md` | Created | Workspace rules, memory rules customized for emotional focus |
| `MEMORY.md` | Created | Long-term memory template (who Rose is, goals, emotional patterns, inside jokes) |
| `HEARTBEAT.md` | Created | Periodic check-in checklist for Rose |

### Xiaomi workspace (`~/.openclaw/xiaomi-workspace/`)

| File | Operation | Description |
|---|---|---|
| `SOUL.md` | Created | Butler identity, daily report format, dual-source report flow (local memory first + Supermemory supplement), privacy rules |
| `IDENTITY.md` | Created | Basic identity |
| `USER.md` | Created | Rose's info + all-agent information table |
| `AGENTS.md` | Created | Workspace rules, memory rules customized for progress tracking |
| `MEMORY.md` | Created | Agent status table, Rose's trends, pending items, report log |
| `HEARTBEAT.md` | Created | Daily report (9 PM PST) + weekly review |

### Global config (`~/.openclaw/openclaw.json`)

| Section | Description |
|---|---|
| `agents.list` | Added Lingro and Xiaomi agents with their workspace and agentDir paths |
| `channels.telegram` | Migrated from single-bot to multi-account format, one botToken per agent |
| `bindings` | Added three binding rules mapping agentId to telegram accountId |
| `plugins` | Added Supermemory plugin config with custom container tags enabled |

---

## Takeaways

Looking back after building this system, the most valuable lessons:

1. **Agent personality needs examples, not just descriptions.** Especially for speaking style — without examples, Claude defaults to "polite AI" mode.
2. **Multi-agent config comes down to three things:** `agents.list` defines agents, `accounts` defines bots, `bindings` connects them.
3. **Local memory files are the most reliable data source.** Each agent writes daily activity to `memory/YYYY-MM-DD.md`; the butler reads these files directly for daily reports. Supermemory is a nice-to-have, not a requirement.
4. **Privacy boundaries should be enforced by information structure, not just prompts.** Lingro's memory file has a status tag on line 1; Xiaomi only reads that line. Much more reliable than "please don't look at the details below."
5. **When things break, check logs first (`openclaw logs --follow`), then config.** Most issues are config format errors or process conflicts.

The design philosophy: **each agent has its own soul (SOUL.md), its own memory (`memory/` directory + Supermemory), its own communication channel (Telegram bot), and they share a thin layer of status information through local memory files.** They each mind their own business, but they're all there for the same person.

---

## References

- [OpenClaw GitHub](https://github.com/nichochar/openclaw)
- [Supermemory](https://supermemory.ai)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Quartz v4](https://quartz.jzhao.xyz)
