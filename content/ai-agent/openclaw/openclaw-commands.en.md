---
title: "OpenClaw Command Reference"
date: 2026-03-06
tags:
  - OpenClaw
  - Reference
lang: en
chinese: ai-agent/openclaw/openclaw-commands
---

> 🌐 [阅读中文版](./openclaw-commands.md)

Quick reference for common OpenClaw commands. When something goes wrong: check logs first, then config.

---

## Gateway

```bash
openclaw gateway start          # Start
openclaw gateway stop           # Stop
openclaw gateway restart        # Restart (required after config changes)
openclaw gateway status         # Check status
```

---

## Logs & Diagnostics

```bash
openclaw logs                   # View logs
openclaw logs --follow          # Stream live logs (best for debugging)
openclaw doctor                 # Full health check
```

---

## Agents

```bash
openclaw agents list            # List all agents
openclaw agents status lingro   # Check a specific agent's status
```

---

## Pairing

```bash
openclaw pairing list                          # List pending requests
openclaw pairing approve telegram XXXXXXXX     # Approve a pairing
```

---

## Cron (Scheduled Tasks)

```bash
openclaw cron list              # List all jobs
openclaw cron run <job-id>      # Trigger manually right now
openclaw cron runs --id <id>    # View run history
openclaw cron edit <id> --message "new prompt"   # Edit a job
openclaw cron remove <id>       # Delete a job
```

### Cron Expression Reference

```
min hour day month weekday
0 11 * * *    Daily at 11:00
0 21 * * *    Daily at 21:00
0 9 * * 1     Every Monday at 9:00
0 9,18 * * *  Daily at 9:00 and 18:00
0 */4 * * *   Every 4 hours
```

---

## Supermemory

```bash
openclaw supermemory status     # Check connection (requires plugin + Gateway running)
```

---

## Plugins

```bash
openclaw plugin install @supermemory/openclaw-supermemory   # Install plugin
openclaw plugin list            # List installed plugins
```

---

## Browser Extension

```bash
openclaw browser extension install   # Install Chrome extension (for Browser Relay)
```

---

## Common Scenarios

| Situation | Command |
|-----------|---------|
| Changed openclaw.json | `openclaw gateway restart` |
| Bot not responding | `openclaw logs --follow` → look for errors |
| Cron not triggering | `openclaw cron runs --id <id>` → check history |
| New bot needs pairing | `openclaw pairing list` → `approve` |
| Diagnose everything | `openclaw doctor` |
