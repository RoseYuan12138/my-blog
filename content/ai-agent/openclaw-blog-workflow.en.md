---
title: "I Built a 24/7 Knowledge Manager with Mac Mini + OpenClaw"
date: 2026-03-01
tags:
  - AI Agent
  - OpenClaw
  - Quartz
  - knowledge management
  - Mac Mini
lang: en
chinese: ai-agent/openclaw-blog-workflow
---

> 🌐 [中文版](./openclaw-blog-workflow.md)

## Why Bother

As working professionals, we learn something new every day — a new algorithm, a debugging trick, an insightful paper, a useful tool. But if these bits of knowledge only stay in our heads or scattered across chat logs and random notes, most of it fades within weeks.

The real value of knowledge lies in **compound interest**. A concept you jot down today might solve a critical problem three months later. Notes you organized a year ago might become the backbone of a technical proposal. Isolated knowledge fragments, once structured and connected, create far more value than the sum of their parts — that's the power of 1+1 > 2.

But here's the problem: **who has time to organize notes every day?**

Work is exhausting enough. Opening an editor after hours, coming up with titles, fixing formatting, running git push... Most people's blogs (mine included) end up abandoned after a burst of enthusiasm.

So my approach: **delegate the organizing and publishing to an AI agent, and focus on what matters most — learning and thinking.**

I got a Mac Mini 4, keep it running 24/7 with OpenClaw, and use it as my "knowledge manager." Throughout my day, I send a message via chat app, and it organizes my thoughts into structured notes, gets my approval, and publishes to my blog. The whole process feels as natural as texting a coworker.

---

## Architecture Overview

```
Me (phone/laptop)
  │
  │  Send messages anytime via Telegram/Discord
  │  "Note: learned about xxx today..."
  ▼
Mac Mini 4 (running 24/7)
  │
  ├── OpenClaw (AI agent, always-on)
  │     ├── Receives my messages
  │     ├── Organizes into Markdown articles
  │     ├── Sends for my review
  │     └── git push after approval
  │
  └── Quartz blog repo (local clone)
        └── content/  ← all knowledge base articles
              ├── recommender-systems/
              ├── ai-agent/
              ├── astronomy/
              └── ...
                    │
                    │  git push triggers GitHub Actions
                    ▼
              GitHub Pages (auto build & deploy)
              → Blog is live ✅
```

In short: **I send a message → OpenClaw on Mac Mini processes it → auto-publishes to blog**.

---

## Why Mac Mini

OpenClaw needs a machine running 24/7. Using my main laptop isn't practical (closing the lid kills it), and a cloud server adds latency and cost. Mac Mini 4 hits the sweet spot:

- **Silent and power-efficient** — sits in a corner, completely unnoticeable
- **More than enough performance** for OpenClaw + local Git operations
- **macOS ecosystem** — plays nicely with my other Apple devices
- Many in the OpenClaw community bought Mac Minis specifically for this

A Linux server, Raspberry Pi, or old laptop would work too. The Mac Mini is just my personal choice.

---

## Blog Platform: Quartz

The blog runs on [Quartz v4](https://quartz.jzhao.xyz/), an open-source static site generator. I chose it because:

- Content is just Markdown files in a `content/` folder — extremely AI-friendly
- Built for knowledge bases — supports graph view, backlinks, and wikilinks for connecting notes
- Free hosting via GitHub Pages — push to GitHub and it's live

Setup is straightforward (`git clone` → `npm i` → `npx quartz create`). See the [official docs](https://quartz.jzhao.xyz/) for details.

---

## OpenClaw: The Star of the Show

### What It Is

[OpenClaw](https://openclaw.ai/) (formerly Clawdbot / Moltbot) is an open-source AI agent by Peter Steinberger. Unlike ChatGPT or Claude's chat interfaces, **it doesn't just answer questions — it takes action**: reading and writing files, running shell commands, managing calendars, sending emails, controlling browsers.

It runs locally and interfaces through your everyday chat apps (Telegram, Discord, WhatsApp, Signal, etc.). You message it like a coworker, and it executes tasks in the background.

### Why It's Perfect for Blog Management

- **Always-on**: Running on my Mac Mini 24/7, with a heartbeat mechanism for scheduled tasks
- **Chat as UI**: I can send notes from the subway, during lunch, in any spare moment via Telegram. No need to open a laptop
- **Persistent memory**: Context carries across conversations — it remembers my knowledge base structure, writing preferences, and previous articles
- **File system access**: Can directly read/write Markdown files and run git commands on the Mac Mini — exactly what blog management needs
- **Customizable behavior**: `SOUL.md` and skill files let me precisely control what it does and doesn't do

### Key Concepts

Understanding these workspace files is the foundation for configuring the agent:

| File | Purpose | Analogy |
|------|---------|---------|
| `SOUL.md` | Agent's behavioral rules and values | Job description for a new hire |
| `USER.md` | Information about you | Your self-introduction to an assistant |
| `IDENTITY.md` | Agent's identity | Its business card |
| `HEARTBEAT.md` | Scheduled task checklist | Daily/weekly to-do list |

Workspace location on macOS: `/Users/[username]/.openclaw/workspace`

It's a hidden folder (starts with `.`). Easiest way to open it:

```bash
open /Users/minicat/.openclaw/workspace
```

### Security Note

OpenClaw is powerful, but with great power comes great responsibility:

- It requires broad system permissions (file access, command execution) — misconfiguration is risky
- Community skills vary in quality; security researchers have found malicious ones
- Set sensitive operations to require human approval, never expose passwords directly
- One of OpenClaw's own maintainers warned: "If you can't understand how to run a command line, this is far too dangerous of a project for you to use safely"

---

## How I Configured OpenClaw for Blog Management

This is the core of this post. After setting up Quartz and OpenClaw, three problems needed solving:

1. How to teach the bot blog operations
2. How to standardize its writing behavior
3. How to implement review and revision

My approach: **write all rules as documents and let the bot read them.** Don't verbally explain things in conversation — it'll forget. Persistent files ensure it can always reference the rules. Like writing onboarding docs for a new hire — the clearer the docs, the faster they ramp up.

I created two key files in the workspace.

### File 1: `BLOG_INSTRUCTIONS.md` (Technical Operations Manual)

This tells the bot everything on the technical side.

**Repo info**: local path, remote URL, which branch to use.

**Directory structure**: My knowledge base is organized by domain and keeps expanding:

```
content/
├── recommender-systems/
│   ├── index.md
│   ├── algorithms/
│   │   ├── collaborative-filtering.md        # Chinese
│   │   └── collaborative-filtering.en.md     # English
│   └── architecture/
├── ai-agent/
├── astronomy/
└── ...
```

Folder names use lowercase English with hyphens. Subdirectories are created when a domain reaches 3+ articles. Every folder gets an `index.md` overview.

**Frontmatter format**: Standard YAML header for every article with title, date, tags, language, and path to the translated version:

```yaml
---
title: "Collaborative Filtering Explained"
date: 2026-03-01
tags:
  - recommender-systems
  - algorithms
lang: en
chinese: recommender-systems/algorithms/collaborative-filtering
---
```

**Bilingual rules**: Living abroad, I want both Chinese and English versions. Chinese is the primary (`.md`), English is the translation (`.en.md`), with toggle links at the top of each. Quartz doesn't natively support article-level language switching, so this simple approach works for now.

**Git workflow and red lines**: Wait for my approval before pushing. Never touch config files. Never delete existing articles. Mark uncertainties with `[TODO]` instead of making things up.

### File 2: `WRITING_GUIDE.md` (Writing Standards + Review SOP)

This covers the behavioral side — when to write, how to write, how to interact with me.

**Trigger word system** is a key design. Not every message should become an article:

| I say | Bot does |
|-------|----------|
| `Note: ...` | Organize into blog note, send for review |
| `Publish: ...` | Organize and prepare for publishing |
| `Update [article]: ...` | Append to existing article |
| `Translate [article]` | Generate English version |
| No trigger word | Regular chat, no article writing |

**Writing style**: Learning notes — concise, direct, preserving authentic thought process. Each article needs: core concept, key points, code/examples (if any), reference links.

**Knowledge base management**: The bot doesn't just write articles. It proactively maintains the knowledge base — checking if directories need reorganization, updating `index.md` files, reminding me about `[TODO]` items, and adding wikilinks between related articles.

**Review workflow** — the lightest option, all via chat:

```
I send content
  ↓
Bot organizes into Markdown article
  ↓
Sends preview in chat (with suggested file path and tags)
  ↓
I say "OK" → generates English version → quick review → confirm → git push → published ✅
I say "change xxx" → revises → resends full article → loop
I say "save for later" → saves to drafts, no publish
```

Everything happens in Telegram. No need to open a laptop.

---

## Setup Steps

### 1. Place Instruction Files in Workspace

```bash
cp BLOG_INSTRUCTIONS.md /Users/minicat/.openclaw/workspace/
cp WRITING_GUIDE.md /Users/minicat/.openclaw/workspace/
```

### 2. Reference in SOUL.md

```markdown
## Blog Management

You are Rose's personal knowledge base assistant. Before any blog task, read:
- BLOG_INSTRUCTIONS.md (technical operations guide)
- WRITING_GUIDE.md (writing standards and review workflow)

Strictly follow these rules, especially:
- Never auto-push, wait for Rose's confirmation
- Mark uncertain content with [TODO], never fabricate
- Generate bilingual versions for every article
```

### 3. Verify Git Access

```bash
cd /path/to/my-blog
git remote -v
git push --dry-run origin v4
```

### 4. Test It

Send the bot a message in Telegram:

```
Note: Learned about RAG (Retrieval-Augmented Generation) today.
Core flow: query → retrieve → augment prompt → generate.
Reduces LLM hallucinations and enables answering beyond training data.
```

If configured correctly, the bot will organize it into an article, send a preview, and wait for approval.

---

## Impressions After Using It

**What works well**:

- Genuinely lowers the barrier to recording knowledge. Used to need a laptop open; now a quick message works — subway, lunch break, anywhere
- The knowledge base is actually growing, and it's structured. So much easier to find things than random notes
- Auto-generated bilingual versions save tons of effort. Translation quality needs tweaking maybe 20% of the time
- The bot proactively managing knowledge base structure exceeded expectations — it'll suggest "you have 3 embedding-related notes, consider creating a subdirectory"

**Room for improvement**:

- The bot sometimes over-polishes, turning casual expressions into textbook language — need to emphasize "preserve original voice" more in the WRITING_GUIDE
- Bilingual toggle is just a link at the top; not the best UX. May build a proper Quartz component later
- As the knowledge base grows, category boundaries get fuzzy (e.g., "RAG in recommender systems" — does it go under `ai-agent/` or `recommender-systems/`?). Need better cross-referencing

---

## Takeaway

The formula: **Mac Mini (hardware) + OpenClaw (agent) + Quartz (blog) + two instruction files (rules)**.

The key insight: **write rules as documents, let the bot read them.** `BLOG_INSTRUCTIONS.md` for the technical layer (how to operate) and `WRITING_GUIDE.md` for the behavioral layer (how to write, how to review). The bot references these before every task — like onboarding docs for a new hire.

With this system, building a knowledge base becomes as simple as sending a chat message. Over time, it becomes your most valuable personal asset.

---

## References

- [OpenClaw Website](https://openclaw.ai/)
- [Quartz Documentation](https://quartz.jzhao.xyz/)
- [Quartz GitHub](https://github.com/jackyzha0/quartz)
