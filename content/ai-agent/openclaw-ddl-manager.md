---
title: "用 OpenClaw 搭建个人 DDL 管理系统"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - 自动化
  - 任务管理
lang: zh
english: ai-agent/openclaw-ddl-manager.en
---

> 🌐 [Read in English](./openclaw-ddl-manager.en.md)

不想用 Notion，不想维护看板，就想跟 AI 说一句「XX做完了」——这套系统就是为这个场景设计的。用 OpenClaw 的多 Agent 架构，把任务管理变成对话。

## 系统设计

### 四象限分类

任务按照重要性和紧急程度分四类：

| 象限 | 描述 | 例子 |
|---|---|---|
| Q1 重要且紧急 | 必须马上处理 | 论文 deadline、H1B 申请 |
| Q2 重要不紧急 | 规划中推进 | 技术学习、健康习惯 |
| Q3 紧急不重要 | 能委托就委托 | 临时会议、杂事 |
| Q4 不重要不紧急 | 可以砍掉 | 刷视频、无效会议 |

### 三个自动化任务

**晨间提醒（cron，每天 11:00）**

```bash
openclaw cron add \
  --name "晨间任务提醒" \
  --cron "0 11 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "读取 DDL 管理文件，生成今日任务清单：Q1 优先，标出今天必须推进的事项。" \
  --announce \
  --channel telegram \
  --to "YOUR_CHAT_ID"
```

**日报（cron，每天 21:00）**

```bash
openclaw cron add \
  --name "晚间日报" \
  --cron "0 21 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "读取 DDL 管理文件，生成今日日报：完成了什么、还剩什么、明天重点。" \
  --announce \
  --channel telegram \
  --to "YOUR_CHAT_ID"
```

**hourly 巡逻（heartbeat）**

在 `openclaw.json` 配置：

```json
"heartbeat": {
  "every": "1h",
  "target": "last",
  "activeHours": { "start": "10:00", "end": "01:00" }
}
```

在 `HEARTBEAT.md` 里写巡逻逻辑：

```markdown
## DDL 巡逻

- 扫描 DDL 文件，检查是否有 Q1 任务超过 2 天无进展
- 检查是否有任务超过 1 天未收到 Rose 回应
- 如有异常，发送提醒
```

## 提醒策略

两种情况特殊处理，而不是简单催 deadline：

**拖延模式（Q1 超 2 天无进展）**

不说「你的 deadline 快到了」，而是给一个最小可执行步骤：

> 「论文 deadline 还有 5 天，今天只需要做一件事：写完第三章的提纲，30 分钟就够。」

**消失模式（超 1 天不回应）**

升频到每天两次提醒，保持存在感但不施压。

## 用户操作：全口语

不需要填表、不需要打命令，直接说话：

```
新任务：H1B 申请，deadline 4月1日，Q1
XX完成了
XX做了YY（部分进展）
把XX移到Q2
```

Agent（小蜜）负责解析并更新文件，Rose 只管说。

## 归档机制

完成超过 7 天的任务自动移入归档：

```
DDL_archive/
└── 2026-03.md
```

保留记录，但不再出现在日常巡逻里。

## 为什么用多 Agent？

- **小蜜**（管家 Agent）：负责读写 DDL 文件、执行 cron 任务、发提醒
- **Rose**：只负责口语输入，不维护任何格式

这是 [[openclaw-multi-agent-tutorial]] 里讲的多 Agent 分工模式在实际场景里的应用——一个 Agent 专注执行，人只做决策。

## Cron 配置详解

上面的晨间提醒和日报都用了 `openclaw cron add`，这里展开说明。

### Cron 还是 Heartbeat？

简单说：
- **Heartbeat** 适合批量周期性检查（收件箱 + 日历 + 天气一起查），走主 session
- **Cron** 适合精确定时（每天早上 9 点整）、需要隔离 session、或要送到指定频道

DDL 系统的晨间提醒和日报用 cron 更合适，因为时间精确 + 内容可以直接推到 Telegram。hourly 巡逻用 heartbeat，因为它需要主 session 的上下文（了解最近的对话）。

### 参数说明

| 参数 | 说明 |
|---|---|
| `--cron "0 11 * * *"` | 每天 11:00 执行（标准 5 字段 cron 表达式） |
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
0 11 * * *    每天 11:00
0 21 * * *    每天 21:00
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

- Gateway 必须持续运行，cron 才会执行（Mac Mini 别合盖，或者用 `caffeinate` 防休眠，参见 [[openclaw-blog-workflow]]）
- 顶点时刻的 cron（如 `0 * * * *`）默认有最多 5 分钟的随机 stagger，避免集中打 API。固定时间（如 `0 11 * * *`）不受影响
- 想要精确到秒，用 6 字段表达式：`0 0 11 * * *`

## 参考

- [[openclaw-multi-agent-tutorial]] — 多 Agent 协作基础
- [OpenClaw Heartbeat 文档](https://docs.openclaw.ai/gateway/heartbeat)
- [OpenClaw Cron 文档](https://docs.openclaw.ai/automation/cron-jobs)
- [Cron vs Heartbeat 选择指南](https://docs.openclaw.ai/automation/cron-vs-heartbeat)
