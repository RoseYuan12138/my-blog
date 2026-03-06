---
title: "OpenClaw Setup Tips: web_search, Preventing Sleep & Scheduled Reports"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - configuration
  - automation
lang: en
chinese: ai-agent/openclaw-tips-websearch-caffeinate-cron
---

> 🌐 [中文版](./openclaw-tips-websearch-caffeinate-cron.md)

Three things that make running an OpenClaw agent day-to-day a lot smoother: enabling web search, keeping your Mac awake, and setting up a scheduled daily report.

## Enabling web_search

OpenClaw's `web_search` tool uses Brave Search by default. You'll need to get your own API key.

**Steps:**

1. Sign up at [Brave Search API](https://brave.com/search/api/)
2. In the dashboard, select the **Data for Search** plan — **not** "Data for AI" (that one isn't compatible)
3. Generate an API key

**Configure it (recommended):**

```bash
openclaw configure --section web
```

This stores the key in `~/.openclaw/openclaw.json`:

```json5
{
  tools: {
    web: {
      search: {
        provider: "brave",
        apiKey: "YOUR_BRAVE_API_KEY",
      },
    },
  },
}
```

Alternatively, set the `BRAVE_API_KEY` environment variable (add it to `~/.openclaw/.env`).

Once configured, the agent can use `web_search` — just ask it to "look up…" and it triggers automatically.

**Other supported providers:**

| Provider | Description | API Key |
|---|---|---|
| Brave (default) | Fast, structured results, free tier available | `BRAVE_API_KEY` |
| Perplexity | AI-synthesized answers with citations | `OPENROUTER_API_KEY` or `PERPLEXITY_API_KEY` |
| Gemini | Google Search grounding | `GEMINI_API_KEY` |

If no provider is explicitly set, OpenClaw auto-detects based on available keys (Brave → Gemini → Kimi → Perplexity → Grok).

---

## Preventing Mac Sleep (caffeinate)

The agent runs on a local Mac. If the Mac sleeps, the Gateway goes down and scheduled tasks stop. Use the built-in `caffeinate` command:

```bash
caffeinate -i -m
```

- `-i`: prevent idle sleep (system won't sleep when idle)
- `-m`: prevent disk idle sleep

Keep the terminal in the foreground and it stays active. To start it alongside the Gateway:

```bash
#!/bin/bash
caffeinate -i -m &
openclaw gateway start
```

---

## Scheduled Daily Reports with OpenClaw Cron

### Cron or Heartbeat?

Quick rule of thumb:
- **Heartbeat** — batches multiple periodic checks (inbox + calendar + weather) in the main session
- **Cron** — precise scheduling (exactly 9:00 AM), isolated session, or delivery to a specific channel

Daily reports fit cron better: exact timing + push directly to Telegram.

### Setting Up a Daily Report

```bash
openclaw cron add \
  --name "Daily Report" \
  --cron "0 9 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "Generate today's daily report: summarize yesterday's activities, today's calendar events, and anything worth noting." \
  --announce \
  --channel telegram \
  --to "YOUR_TELEGRAM_CHAT_ID"
```

**Parameter breakdown:**

| Flag | Description |
|---|---|
| `--cron "0 9 * * *"` | Run every day at 9:00 (standard 5-field cron expression) |
| `--tz "America/Los_Angeles"` | Timezone; defaults to Gateway host timezone if omitted |
| `--session isolated` | Runs in a fresh isolated session, doesn't pollute main session history |
| `--message` | The prompt sent to the agent |
| `--announce` | Deliver output to the target channel after the run |
| `--channel telegram` | Delivery channel |
| `--to` | Telegram chat ID (personal or group) |

### Cron Expression Cheatsheet

```
┌────────── minute (0-59)
│ ┌──────── hour (0-23)
│ │ ┌────── day of month (1-31)
│ │ │ ┌──── month (1-12)
│ │ │ │ ┌── day of week (0-6, 0=Sunday)
│ │ │ │ │
0 9 * * *     Every day at 9:00
0 9 * * 1     Every Monday at 9:00
0 9,18 * * *  Every day at 9:00 and 18:00
0 */4 * * *   Every 4 hours
```

### What Is an Isolated Session?

`--session isolated` runs the job in a brand-new session (`cron:<jobId>`) with no prior conversation context. Benefits:

- Report content doesn't pile up in your main session history
- Can use `--model` to specify a different model per job
- Output is delivered via `--announce` directly — the main session doesn't need to wake up to handle it

### Managing Cron Jobs

```bash
# List all jobs
openclaw cron list

# Trigger a job manually right now
openclaw cron run <job-id>

# View run history
openclaw cron runs --id <job-id>

# Edit a job
openclaw cron edit <job-id> --message "Updated prompt"

# Remove a job
openclaw cron remove <job-id>
```

### A Few Things to Know

- The Gateway must be running continuously for cron to work (use `caffeinate` above)
- Top-of-hour schedules like `0 * * * *` get a deterministic stagger of up to 5 minutes to spread API load. Fixed-time expressions like `0 9 * * *` run exactly on schedule
- For second-level precision, use a 6-field expression: `0 0 9 * * *`

---

## References

- [Brave Search API](https://brave.com/search/api/)
- [OpenClaw Web Tools Docs](https://docs.openclaw.ai/tools/web)
- [OpenClaw Cron Jobs Docs](https://docs.openclaw.ai/automation/cron-jobs)
- [Cron vs Heartbeat Guide](https://docs.openclaw.ai/automation/cron-vs-heartbeat)
