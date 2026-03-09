---
title: "Let Your Butler Agent Track Deadlines: Xiaomi's Daily DDL Routine"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - automation
  - task management
lang: en
chinese: ai-agent/openclaw/openclaw-ddl-manager
---

> 🌐 [中文版](./openclaw-ddl-manager.md)

Every morning at 11am, before I'm fully awake, Xiaomi has already read through my task list and sent me a morning briefing:

> 🌅 Today's Tasks — 2026-03-06
>
> **【Q1 Priority】**
> - H1B Filing — due 4/1, 26 days left, materials submitted ✅
> - Thesis — due 5/15, **recommended: finish Chapter 3 outline today**
>
> **【Q2 Progress】**
> - Browser Relay research — no update (2 days, consider downgrading?)

At 9pm, she sends a daily report. If I've been ignoring reminders for a task for a few days, she switches to "procrastination mode" — no more deadline countdowns, just one minimal next step: "You only need to do one thing today."

This is Xiaomi's daily routine — the butler agent in my multi-agent system, dedicated to making sure I don't drop anything important.

---

## Who Is Xiaomi

In my 3-agent system (full setup in [[openclaw-multi-agent-tutorial]]):

| Agent | Emoji | Role |
|-------|-------|------|
| minicat | 🐱 | Blog assistant — turns notes into articles |
| Lingro | 💜 | Best friend — emotional support and life planning |
| Xiaomi | 🏠 | Butler — task management, progress tracking, coordination, daily reports |

DDL management is Xiaomi's core function. This article covers only Xiaomi's DDL work — how she operates and how to configure it. No Notion, no Kanban boards — just tell the AI "I finished X" and it handles the rest.

---

## System Design

### The Four-Quadrant Classification

Tasks are categorized by importance and urgency:

| Quadrant | Description | Examples |
|---|---|---|
| Q1 Important + Urgent | Handle immediately | Thesis deadline, H1B filing |
| Q2 Important, Not Urgent | Steadily progress | Learning, healthy habits |
| Q3 Urgent, Not Important | Delegate if possible | Ad-hoc meetings, errands |
| Q4 Neither | Cut if possible | Mindless scrolling, useless meetings |

### DDL File Format

`DDL.md` only holds active tasks. Completed tasks are deleted and logged into the daily memory file:

```markdown
# DDL.md - Rose's Task List

<!-- Active tasks only. Completed tasks are removed and logged to memory/YYYY-MM-DD.md. -->

## Q1 - Important + Urgent

<!-- Format: - [ ] Task name | deadline: YYYY-MM-DD | last progress: XX | last updated: YYYY-MM-DD -->

- [ ] H1B filing | deadline: 2026-04-01 | last progress: materials submitted | last updated: 2026-03-06

## Q2 - Important, Not Urgent

## Q3 - Urgent, Not Important

## Q4 - Neither
```

Key point: each task carries a deadline, last progress note, and last updated date. The heartbeat patrol uses these to decide whether a reminder is needed.

### Three Automated Jobs

The entire system runs on three triggers:

| Trigger | When | What |
|---------|------|------|
| Heartbeat | Hourly, 10:00–01:00 | Check DDL for due dates → remind or HEARTBEAT_OK |
| Morning brief | Daily 11:00 | Send today's task overview |
| Daily report | Daily 21:00 | Three-stage reviewed report |

**Morning reminder (cron, daily 11:00)**

```bash
openclaw cron add \
  --name "Morning Task Brief" \
  --cron "0 11 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "Read the DDL management file and generate today's task list: Q1 first, highlight what must move forward today." \
  --announce \
  --channel telegram \
  --to "YOUR_CHAT_ID"
```

The morning reminder only reads DDL.md — no cross-agent communication needed. Output format:

```
🌅 Today's Tasks YYYY-MM-DD

【Q1 Priority】
- [Due today or urgent tasks, with deadlines]

【Q2 Progress】
- [Latest progress on important but not urgent items]

【Reminders】
- [Anything that needs attention, if any]
```

**Daily report (cron, daily 21:00) — Three-stage review**

The daily report isn't just "read file, generate summary." It runs a three-stage review process:

| Stage | Action | Broadcast? |
|-------|--------|------------|
| 1. Data collection | Query each agent for today's data | No |
| 2. Draft review | Compile draft, send back to agents for line-by-line confirmation | No |
| 3. Send | Broadcast the confirmed final report | Yes |

Why three stages? In practice, the butler agent's "understand and synthesize" step is error-prone — it might attribute A's info to B, or use stale memory data. The three stages ensure every piece of information is confirmed by its source.

```bash
openclaw cron add \
  --name "Evening Report" \
  --cron "0 21 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "Run three-stage report: 1.Collect from minicat and lingro 2.Compile and send back for confirmation 3.Broadcast confirmed report" \
  --announce \
  --channel telegram \
  --to "YOUR_CHAT_ID"
```

**Hourly patrol (heartbeat)**

Configure in `openclaw.json`:

```json
"heartbeat": {
  "every": "1h",
  "target": "last",
  "activeHours": { "start": "10:00", "end": "01:00" }
}
```

Add patrol logic to `HEARTBEAT.md` with prioritized checks:

```markdown
## Heartbeat (Hourly)

Read DDL.md and check in priority order:

**Check A: Tasks due today or tomorrow**
→ Remind immediately

**Check B: Q1 tasks with last update date 2+ days ago**
→ Procrastination mode

**Check C: Rose hasn't responded to any reminder in 1+ day**
→ Ghost mode

**None of the above** → Reply HEARTBEAT_OK
```

## Reminder Strategies

Two special cases — handled with care, not nagging:

**Procrastination mode (Check B: Q1, no progress for 2+ days)**

Instead of "your deadline is coming up", give one minimum viable action:

> "Thesis deadline is in 5 days. Today's only job: finish the outline for Chapter 3. Should take 30 minutes."

**Ghost mode (Check C: no response for 1+ day)**

Bump up to twice-daily reminders — stay present without adding pressure.

## User Interface: Plain Speech

No forms, no commands — just talk. The agent (小蜜) parses input and updates DDL.md:

| What the user says | What the agent does |
|-------------------|-------------------|
| "X is done" | Remove from DDL.md, log to `memory/YYYY-MM-DD.md` |
| "Did some work on X: [details]" | Update last progress and date in DDL.md |
| "Change X's deadline to Y" | Update the date in DDL.md |
| "New task: X, deadline Y, Q1" | Add to the corresponding quadrant in DDL.md |
| "Move X to Q2" | Change the task's quadrant |

Rose just talks — no file formats to maintain.

## Memory System

Completed tasks don't just get archived — they feed into a two-layer memory system:

**Daily Memory (`memory/YYYY-MM-DD.md`) — The log**

```markdown
# 2026-03-06

## Tasks
- ✅ Completed: H1B materials submitted (13:00 PST)
- 🔄 Progress: Thesis — finished Chapter 3 outline
- ➕ New: Browser Relay research

## Daily Report
- Sent at: 21:48 PST
- minicat: 7 posts/updates today
- Rose status: happy/energized

## Cross-Agent Coordination
- Asked minicat about today's publishing status, confirmed 7 posts pushed

## Other
- Token usage: ~1M tokens/day during heavy sessions_send usage
```

**Long-term Memory (`MEMORY.md`) — Curated knowledge**

Not a log — only things that matter across days:

- Rose's long-term status trends ("she's been tired for the past two weeks" — a cross-day observation)
- Key context (relationships, important preferences)
- System-level lessons (token consumption, workflow bugs)
- Each agent's capability boundaries and known issues

On every session startup, 小蜜 reads today's and yesterday's daily memory plus the long-term MEMORY.md to reconstruct context.

## Why Multi-Agent?

The system runs three agents, each with a clear role:

| Agent | Emoji | Role | Relation to DDL System |
|-------|-------|------|----------------------|
| 小蜜 | 🏠 | Butler / Coordinator | Runs DDL patrol, morning brief, daily report; maintains task files |
| minicat | 🐱 | Blog assistant | Provides daily blog activity data for reports |
| 凌若 | 💜 | Best friend / Coach | Provides Rose's daily status tag for reports |

小蜜 is the hub — doesn't write blogs (minicat's job), doesn't do emotional support (凌若's job). It only coordinates and executes.

This is the multi-agent division of labor from [[openclaw-multi-agent-tutorial]] applied to a real use case. Key design principles:

**Transparent agent communication**

After 小蜜 communicates with other agents via `sessions_send`, it must broadcast the content to the Telegram group. Rose can always ask "what did you tell minicat?" and get a fully transparent answer. The only exception: stages 1-2 of the daily report don't broadcast, because the back-and-forth confirmation is too noisy — the final version goes out all at once.

**Privacy boundaries**

凌若 and Rose's private conversations should never appear in any output. When 小蜜 reads 凌若's memory, it only reads the first-line status tag (e.g., "happy/energized"), never the actual conversation content. The daily report only writes "Rose status: [tag]" for 凌若's section.

**No decisions on Rose's behalf**

小蜜 provides information and suggestions, but the choice is always Rose's. It doesn't make decisions for other agents — it only coordinates and notifies.

## Cron Configuration Details

The morning reminder and daily report above both use `openclaw cron add`. Here's a deeper dive.

### Cron vs. Heartbeat

In short:
- **Heartbeat** is for batch periodic checks (inbox + calendar + weather all at once), running in the main session
- **Cron** is for precise timing (every day at exactly 9 AM), isolated sessions, or pushing to specific channels

The DDL system's morning reminder and daily report use cron because they need precise timing and can push directly to Telegram. The hourly patrol uses heartbeat because it needs the main session's context (recent conversation history).

### Parameter Reference

| Parameter | Description |
|---|---|
| `--cron "0 11 * * *"` | Execute daily at 11:00 (standard 5-field cron expression) |
| `--tz "America/Los_Angeles"` | Timezone; defaults to Gateway host timezone if omitted |
| `--session isolated` | Run in an isolated session, keeps main session history clean |
| `--message` | The prompt sent to the agent |
| `--announce` | Push output to a specified channel when done |
| `--channel telegram` | Push channel |
| `--to` | Telegram chat ID (personal or group) |

### Cron Expression Cheat Sheet

```
┌────────── minute (0-59)
│ ┌──────── hour (0-23)
│ │ ┌────── day of month (1-31)
│ │ │ ┌──── month (1-12)
│ │ │ │ ┌── day of week (0-6, 0=Sunday)
│ │ │ │ │
0 11 * * *    Every day at 11:00
0 21 * * *    Every day at 21:00
0 9 * * 1     Every Monday at 9:00
0 9,18 * * *  Every day at 9:00 and 18:00
0 */4 * * *   Every 4 hours
```

### What Is an Isolated Session?

Cron's `--session isolated` creates a **brand new independent session** under `cron:<jobId>`. Each run starts with a fresh context and no conversation history. Benefits:

- Keeps repeated report content out of the main session
- Can use `--model` to specify a different model
- Output goes directly via `--announce` — the main session doesn't need to wake up

### Managing Cron Jobs

```bash
# List all jobs
openclaw cron list

# Trigger a job manually
openclaw cron run <job-id>

# View run history
openclaw cron runs --id <job-id>

# Edit a job
openclaw cron edit <job-id> --message "new prompt"

# Delete a job
openclaw cron remove <job-id>
```

### Notes

- The Gateway must be running for cron jobs to execute (don't close your Mac's lid, or use `caffeinate` to prevent sleep — see [[openclaw-blog-workflow]])
- On-the-hour cron jobs (like `0 * * * *`) have up to 5 minutes of random stagger by default to avoid API spikes. Fixed-time jobs (like `0 11 * * *`) are not affected
- For second-level precision, use a 6-field expression: `0 0 11 * * *`

## References

- [[openclaw-multi-agent-tutorial]] — multi-agent collaboration basics
- [OpenClaw Heartbeat Docs](https://docs.openclaw.ai/gateway/heartbeat)
- [OpenClaw Cron Docs](https://docs.openclaw.ai/automation/cron-jobs)
- [Cron vs Heartbeat Guide](https://docs.openclaw.ai/automation/cron-vs-heartbeat)
