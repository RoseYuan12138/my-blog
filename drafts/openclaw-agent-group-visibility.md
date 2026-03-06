---
title: "让多 Agent 通信在 Telegram 群里透明可见"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - 多 Agent
  - Telegram
lang: zh
english: ai-agent/openclaw-agent-group-visibility.en
---

> 🌐 [Read in English](./openclaw-agent-group-visibility.en.md)

多 Agent 系统跑起来之后，有个问题：Agent 之间用 `sessions_send` 互发消息，Rose 完全看不见在发什么。这篇记录如何建一个 Telegram 群，让所有跨 Agent 的协调消息都透明呈现。

## 问题背景

在 [[openclaw-multi-agent-tutorial]] 里搭好的多 Agent 系统中，小蜜可以发消息给 minicat，minicat 再回复小蜜——但这些消息都走 `sessions_send`，只在 Gateway 内部流转，Rose 作为旁观者完全不知道发生了什么。

解决方案：建一个 Telegram 群，把所有 bot 都拉进去，让协调消息也推到群里。

## 实现步骤

### 1. 建群并拉入所有 bot

在 Telegram 里新建群组，把涉及到的所有 bot 账号都添加进来（比如 @xiaomi_bot、@minicat_bot 等）。

### 2. 找到群的 chat ID

麻烦点在这里——OpenClaw 已经在消费 Telegram 的 `getUpdates`，直接调 API 看不到群消息。需要从 Gateway 日志里捞：

```bash
grep "chatId" /tmp/openclaw/openclaw-YYYY-MM-DD.log | grep "group\|supergroup"
```

找到类似 `-5104805503` 这样的负数 ID，那就是群的 chat ID。

### 3. 配置群白名单

OpenClaw 默认 `groupPolicy` 是 allowlist 且没有配白名单，群消息会被 silent drop（静默丢弃，不报错）。需要在 `openclaw.json` 里把群 ID 加进每个 Agent 的白名单：

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

### 4. 开启跨 Agent 通信权限

```json
{
  "tools": {
    "sessions": { "visibility": "all" },
    "agentToAgent": { "enabled": true }
  }
}
```

### 5. 发消息时同时发群

Agent 在发跨 Agent 通知的同时，额外发一条到群里：

```
message(action=send, target="-5104805503", message="[minicat → 小蜜] 博客草稿已准备好，等待确认")
```

Rose 就能在群里实时看到 Agent 之间在说什么。

## 踩坑记录

**坑一：群消息 silent drop**

`groupPolicy` 默认是 allowlist，但没有配 `groupAllowFrom`，等于白名单为空，所有群消息都被静默丢弃。症状是发了没反应、也没报错，很难发现。解法：按上面步骤补上白名单。

**坑二：看不到群的 chat ID**

直接调 Telegram Bot API 的 `getUpdates` 是看不到的，因为 OpenClaw 已经在消费这个接口，不会有残留。只能从 Gateway 日志里捞，关键词是 `chatId` + `group`。

**坑三：重启断连**

修改 `openclaw.json` 后需要 `openclaw gateway restart`，会有短暂断连（几秒）。配置好之后正常运行不需要重启。

## 效果

配好之后，Rose 在 Telegram 群里能实时看到 Agent 之间的协调消息：

```
小蜜 → minicat：Rose 想把 DDL 系统做成博客，请整理草稿
minicat → 小蜜：收到，草稿已发给 Rose 确认
```

小蜜每次给其他 Agent 发协调指令，都会同步一条到群里。**管家的每一条指令，主人都看得见。**

这让多 Agent 系统从黑盒变成玻璃房——协作透明，信任建立在可见性上。

## 参考

- [[openclaw-multi-agent-tutorial]] — 多 Agent 系统搭建基础
- [OpenClaw 群组配置文档](https://docs.openclaw.ai/channels/groups)
- [Telegram Bot API](https://core.telegram.org/bots/api#getupdates)
