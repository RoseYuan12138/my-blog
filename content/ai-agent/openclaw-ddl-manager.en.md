---
title: "Building a Personal DDL Manager with OpenClaw"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - automation
  - task management
lang: en
chinese: ai-agent/openclaw-ddl-manager
---

> 🌐 [中文版](./openclaw-ddl-manager.md)

No Notion, no Kanban boards — just tell the AI "I finished X" and it handles the rest. This system uses OpenClaw's multi-agent architecture to turn task management into a conversation.

## System Design

### The Four-Quadrant Classification

Tasks are categorized by importance and urgency:

| Quadrant | Description | Examples |
|---|---|---|
| Q1 Important + Urgent | Handle immediately | Thesis deadline, H1B filing |
| Q2 Important, Not Urgent | Steadily progress | Learning, healthy habits |
| Q3 Urgent, Not Important | Delegate if possible | Ad-hoc meetings, errands |
| Q4 Neither | Cut if possible | Mindless scrolling, useless meetings |

### Three Automated Jobs

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

**Daily report (cron, daily 21:00)**

```bash
openclaw cron add \
  --name "Evening Report" \
  --cron "0 21 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "Read the DDL management file and generate today's report: what got done, what's left, tomorrow's priorities." \
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

Add patrol logic to `HEARTBEAT.md`:

```markdown
## DDL Patrol

- Scan DDL file for Q1 tasks with no progress in 2+ days
- Check for tasks with no response from Rose in 1+ day
- Send an alert if anything needs attention
```

## Reminder Strategies

Two special cases — handled with care, not nagging:

**Procrastination mode (Q1, no progress for 2+ days)**

Instead of "your deadline is coming up", give one minimum viable action:

> "Thesis deadline is in 5 days. Today's only job: finish the outline for Chapter 3. Should take 30 minutes."

**Ghost mode (no response for 1+ day)**

Bump up to twice-daily reminders — stay present without adding pressure.

## User Interface: Plain Speech

No forms, no commands — just talk:

```
New task: H1B filing, deadline April 1, Q1
X is done
Did some work on Y (partial progress)
Move X to Q2
```

The agent (小蜜) parses the input and updates the file. Rose just talks.

## Archiving

Tasks completed more than 7 days ago get moved to the archive:

```
DDL_archive/
└── 2026-03.md
```

Keeps the record, removes it from daily patrol.

## Why Multi-Agent?

- **小蜜** (butler agent): reads/writes the DDL file, runs cron jobs, sends reminders
- **Rose**: just talks — no file formats to maintain

This is the multi-agent division of labor from [[openclaw-multi-agent-tutorial]] applied to a real use case — one agent handles execution, the human handles decisions.

## References

- [[openclaw-tips-websearch-caffeinate-cron]] — cron configuration in detail
- [[openclaw-multi-agent-tutorial]] — multi-agent collaboration basics
- [OpenClaw Heartbeat Docs](https://docs.openclaw.ai/gateway/heartbeat)
- [OpenClaw Cron Docs](https://docs.openclaw.ai/automation/cron-jobs)
