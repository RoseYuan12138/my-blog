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

## 参考

- [[openclaw-tips-websearch-caffeinate-cron]] — cron 配置详解
- [[openclaw-multi-agent-tutorial]] — 多 Agent 协作基础
- [OpenClaw Heartbeat 文档](https://docs.openclaw.ai/gateway/heartbeat)
- [OpenClaw Cron 文档](https://docs.openclaw.ai/automation/cron-jobs)
