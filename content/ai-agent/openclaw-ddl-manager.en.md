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
