---
title: "Making Multi-Agent Communication Visible in a Telegram Group"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - multi-agent
  - Telegram
lang: en
chinese: ai-agent/openclaw-agent-group-visibility
---

> 🌐 [中文版](./openclaw-agent-group-visibility.md)

Once a multi-agent system is running, there's an invisible problem: agents talk to each other via `sessions_send`, but none of it is visible to you. This post covers how to set up a Telegram group so all cross-agent coordination is transparent.

## The Problem

In the multi-agent system from [[openclaw-multi-agent-tutorial]], 小蜜 can message minicat and minicat can reply — but all of this flows through `sessions_send` inside the Gateway. Rose, as an observer, has no idea what's happening between agents.

The fix: create a Telegram group, add all the bots, and have agents CC the group whenever they coordinate.

## Setup Steps

### 1. Create a group and add all bots

Create a new Telegram group and add all relevant bot accounts (e.g. @xiaomi_bot, @minicat_bot, etc.).

### 2. Find the group's chat ID

This is the tricky part — OpenClaw is already consuming Telegram's `getUpdates`, so you can't just call the API directly. You need to find the chat ID from the Gateway logs:

```bash
grep "chatId" /tmp/openclaw/openclaw-YYYY-MM-DD.log | grep "group\|supergroup"
```

Look for a negative number like `-5104805503` — that's your group chat ID.

### 3. Configure the group allowlist

OpenClaw's default `groupPolicy` is allowlist with no entries configured, which means all group messages get silently dropped (no error, no log). Add the group ID to each agent's allowlist in `openclaw.json`:

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

### 4. Enable cross-agent communication

```json
{
  "tools": {
    "sessions": { "visibility": "all" },
    "agentToAgent": { "enabled": true }
  }
}
```

### 5. Send to the group alongside agent-to-agent messages

When an agent sends a cross-agent notification, it also posts a copy to the group:

```
message(action=send, target="-5104805503", message="[minicat → 小蜜] Blog draft ready, waiting for confirmation")
```

Rose can now see what agents are saying to each other in real time.

## Pitfalls

**Pitfall 1: Silent drop with no errors**

The default `groupPolicy` is allowlist with an empty `groupAllowFrom` — equivalent to blocking everything. Group messages are dropped silently: no response, no error. Hard to diagnose. Fix: add the group ID to the allowlist as shown above.

**Pitfall 2: Can't see the chat ID**

Calling Telegram Bot API's `getUpdates` directly won't work because OpenClaw is already consuming the webhook. The only way is to read it from the Gateway logs using the `chatId` + `group` keywords.

**Pitfall 3: Brief disconnect on restart**

After editing `openclaw.json`, run `openclaw gateway restart`. There'll be a few seconds of downtime. Once configured, normal operation doesn't need restarts.

## Result

After setup, Rose sees agent coordination in the Telegram group in real time:

```
小蜜 → minicat: Rose wants to turn the DDL system into a blog post, please draft it
minicat → 小蜜: Received, draft sent to Rose for review
```

Every instruction the butler sends, the owner can see.

This turns a multi-agent system from a black box into a glass room — collaboration is transparent, and trust is built on visibility.

## References

- [[openclaw-multi-agent-tutorial]] — multi-agent system basics
- [OpenClaw Groups Configuration](https://docs.openclaw.ai/channels/groups)
- [Telegram Bot API](https://core.telegram.org/bots/api#getupdates)
