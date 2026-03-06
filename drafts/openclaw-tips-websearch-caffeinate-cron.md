---
title: "OpenClaw 实用配置：web_search、防休眠与定时日报"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - 工具配置
  - 自动化
lang: zh
english: ai-agent/openclaw-tips-websearch-caffeinate-cron.en
---

> 🌐 [Read in English](./openclaw-tips-websearch-caffeinate-cron.en.md)

三个让 OpenClaw Agent 用起来更顺手的配置：联网搜索、防止 Mac 休眠、以及定时推送日报。

## 给 Agent 加上 web_search

OpenClaw 的 `web_search` 工具默认走 Brave Search API，需要自己申请 API key。

**申请步骤：**

1. 去 [Brave Search API](https://brave.com/search/api/) 注册账号
2. 在 dashboard 选择 **Data for Search** 方案（注意：**不是** Data for AI，那个不兼容）
3. 生成 API key

**配置方式（推荐）：**

```bash
openclaw configure --section web
```

会把 key 存进 `~/.openclaw/openclaw.json`，对应字段是：

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

也可以直接设环境变量 `BRAVE_API_KEY`（放在 `~/.openclaw/.env`）。

配好之后，Agent 就能用 `web_search` 工具了，对话里问「搜一下…」会自动触发。

**其他 provider 可选项：**

| Provider | 特点 | API Key |
|---|---|---|
| Brave（默认） | 快、结构化结果、有免费额度 | `BRAVE_API_KEY` |
| Perplexity | AI 综合答案 + 引用 | `OPENROUTER_API_KEY` 或 `PERPLEXITY_API_KEY` |
| Gemini | Google Search grounding | `GEMINI_API_KEY` |

没有显式配置 provider 时，OpenClaw 会按 key 的存在顺序自动探测（Brave → Gemini → Kimi → Perplexity → Grok）。

---

## 防止 Mac 休眠（caffeinate）

Agent 跑在本地 Mac 上，一旦 Mac 进入睡眠，Gateway 就断了，定时任务也会停。用系统自带的 `caffeinate` 命令解决：

```bash
caffeinate -i -m
```

- `-i`：阻止 idle 休眠（系统空闲时不睡）
- `-m`：阻止磁盘 idle sleep

Terminal 保持前台运行就持续生效。想配合 Gateway 一起启动，可以写个 shell 脚本：

```bash
#!/bin/bash
caffeinate -i -m &
openclaw gateway start
```

---

## 用 OpenClaw Cron 配置定时日报

### Cron 还是 Heartbeat？

简单说：
- **Heartbeat** 适合批量周期性检查（收件箱 + 日历 + 天气一起查），走主 session
- **Cron** 适合精确定时（每天早上 9 点整）、需要隔离 session、或要送到指定频道

日报用 cron 更合适，因为时间精确 + 内容可以直接推到 Telegram。

### 配置日报的命令

```bash
openclaw cron add \
  --name "每日日报" \
  --cron "0 9 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "生成今日日报：总结昨天的博客活动、今天的日历事项、以及任何值得关注的事。" \
  --announce \
  --channel telegram \
  --to "YOUR_TELEGRAM_CHAT_ID"
```

**参数说明：**

| 参数 | 说明 |
|---|---|
| `--cron "0 9 * * *"` | 每天 9:00 执行（标准 5 字段 cron 表达式） |
| `--tz "America/Los_Angeles"` | 时区，不加默认用 Gateway 主机时区 |
| `--session isolated` | 跑在独立 session，不污染主 session 历史 |
| `--message` | 给 Agent 的提示词 |
| `--announce` | 完成后把输出推送到指定频道 |
| `--channel telegram` | 推送渠道 |
| `--to` | Telegram chat ID（可以是个人或群组） |

### Cron 表达式速查

```
┌────────── 分钟 (0-59)
│ ┌──────── 小时 (0-23)
│ │ ┌────── 日 (1-31)
│ │ │ ┌──── 月 (1-12)
│ │ │ │ ┌── 周 (0-6，0=周日)
│ │ │ │ │
0 9 * * *     每天 9:00
0 9 * * 1     每周一 9:00
0 9,18 * * *  每天 9:00 和 18:00
0 */4 * * *   每 4 小时
```

### Isolated Session 是什么？

Cron 的 `--session isolated` 会在 `cron:<jobId>` 下开一个**全新的独立 session**，每次运行都是全新上下文，不带任何历史对话。好处是：

- 不会把重复的日报内容堆进主 session
- 可以用 `--model` 指定不同模型
- 输出通过 `--announce` 直接推送，不需要主 session 醒来处理

### 管理 Cron 任务

```bash
# 查看所有任务
openclaw cron list

# 立刻手动触发一次
openclaw cron run <job-id>

# 查看运行历史
openclaw cron runs --id <job-id>

# 修改任务
openclaw cron edit <job-id> --message "新的提示词"

# 删除任务
openclaw cron remove <job-id>
```

### 注意事项

- Gateway 必须持续运行，cron 才会执行（配合上面的 caffeinate）
- 顶点时刻的 cron（如 `0 * * * *`）默认有最多 5 分钟的随机 stagger，避免集中打 API。固定时间（如 `0 9 * * *`）不受影响
- 想要精确到秒，用 6 字段表达式：`0 0 9 * * *`

---

## 参考

- [Brave Search API](https://brave.com/search/api/)
- [OpenClaw Web Tools 文档](https://docs.openclaw.ai/tools/web)
- [OpenClaw Cron Jobs 文档](https://docs.openclaw.ai/automation/cron-jobs)
- [Cron vs Heartbeat 选择指南](https://docs.openclaw.ai/automation/cron-vs-heartbeat)
