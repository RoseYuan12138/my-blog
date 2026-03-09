---
title: "OpenClaw 命令速查"
date: 2026-03-06
tags:
  - OpenClaw
  - 速查
lang: zh
english: ai-agent/openclaw/openclaw-commands.en
---

> 🌐 [Read in English](./openclaw-commands.en.md)

常用命令快速参考。出问题先看日志，再查配置。

---

## Gateway

```bash
openclaw gateway start          # 启动
openclaw gateway stop           # 停止
openclaw gateway restart        # 重启（改配置后必须）
openclaw gateway status         # 查看状态
```

---

## 日志 & 诊断

```bash
openclaw logs                   # 查看日志
openclaw logs --follow          # 实时流式日志（调试首选）
openclaw doctor                 # 全面健康检查
```

---

## Agent

```bash
openclaw agents list            # 列出所有 Agent
openclaw agents status lingro   # 查看某个 Agent 状态
```

---

## Pairing（配对）

```bash
openclaw pairing list                          # 列出待审批请求
openclaw pairing approve telegram XXXXXXXX     # 批准配对
```

---

## Cron（定时任务）

```bash
openclaw cron list              # 查看所有任务
openclaw cron run <job-id>      # 立刻手动触发一次
openclaw cron runs --id <id>    # 查看运行历史
openclaw cron edit <id> --message "新提示词"   # 修改任务
openclaw cron remove <id>       # 删除任务
```

### Cron 表达式速查

```
分 时 日 月 周
0 11 * * *    每天 11:00
0 21 * * *    每天 21:00
0 9 * * 1     每周一 9:00
0 9,18 * * *  每天 9:00 和 18:00
0 */4 * * *   每 4 小时
```

---

## Supermemory

```bash
openclaw supermemory status     # 查看连接状态（需插件已安装 + Gateway 运行）
```

---

## Plugin（插件）

```bash
openclaw plugin install @supermemory/openclaw-supermemory   # 安装插件
openclaw plugin list            # 列出已安装插件
```

---

## Browser Extension

```bash
openclaw browser extension install   # 安装 Chrome 扩展（用于 Browser Relay）
```

---

## 常见场景

| 场景 | 命令 |
|------|------|
| 改了 openclaw.json | `openclaw gateway restart` |
| Bot 不回消息 | `openclaw logs --follow` → 看是否有报错 |
| Cron 没触发 | `openclaw cron runs --id <id>` 查历史 |
| 新 Bot 需要配对 | `openclaw pairing list` → `approve` |
| 诊断所有问题 | `openclaw doctor` |
