---
title: "让管家 Agent 替你追 Deadline：小蜜的 DDL 管理日常"
date: 2026-03-06
tags:
  - OpenClaw
  - AI Agent
  - 自动化
  - 任务管理
lang: zh
english: ai-agent/openclaw/openclaw-ddl-manager.en
---

> 🌐 [Read in English](./openclaw-ddl-manager.en.md)

每天早上 11 点，我还没完全清醒，小蜜已经读完了我的任务清单，给我发了一条晨间消息：

> 🌅 今日任务 2026-03-06
>
> **【Q1 重点】**
> - H1B 申请 — 截止 4/1，还剩 26 天，材料已提交 ✅
> - 论文 — 截止 5/15，**建议今天完成第三章提纲**
>
> **【Q2 进度】**
> - Browser Relay 调研 — 无进展（2 天未更新，考虑降级？）

晚上 9 点，她会发日报。如果我有几天没回应某个任务的提醒，她会切换到"拖延模式"，不再报数字，只给一个最小可执行步骤：「今天只需要做一件事。」

这是小蜜的日常——我多 Agent 系统里的管家，专门负责让我不漏掉重要的事。

---

## 小蜜是谁

在我的 3-Agent 系统里（完整搭建过程见 [[openclaw-multi-agent-tutorial]]）：

| Agent | Emoji | 职责 |
|-------|-------|------|
| minicat | 🐱 | 博客助手，把学到的东西整理成文章 |
| 凌若 | 💜 | 闺蜜，情绪支持和人生规划 |
| 小蜜 | 🏠 | 管家，任务管理、进度追踪、跨 Agent 协调、日报 |

DDL 管理是小蜜最核心的功能。这篇文章只讲小蜜的 DDL 部分——她是怎么工作的，怎么配置的。不想用 Notion，不想维护看板，就想跟 AI 说一句「XX 做完了」——这套系统就是为这个场景设计的。

---

## 系统设计

### 四象限分类

任务按照重要性和紧急程度分四类：

| 象限 | 描述 | 例子 |
|---|---|---|
| Q1 重要且紧急 | 必须马上处理 | 论文 deadline、H1B 申请 |
| Q2 重要不紧急 | 规划中推进 | 技术学习、健康习惯 |
| Q3 紧急不重要 | 能委托就委托 | 临时会议、杂事 |
| Q4 不重要不紧急 | 可以砍掉 | 刷视频、无效会议 |

### DDL 文件格式

`DDL.md` 只放活跃任务，完成的任务删除后记入当天的 memory 文件：

```markdown
# DDL.md - Rose 的任务清单

<!-- 只放活跃任务。完成的任务从这里删除，记入当天 memory/YYYY-MM-DD.md。 -->

## Q1 - 重要且紧急

<!-- 格式: - [ ] 任务名 | deadline: YYYY-MM-DD | 最后进展: XX | 最后更新: YYYY-MM-DD -->

- [ ] H1B 申请 | deadline: 2026-04-01 | 最后进展: 材料已提交 | 最后更新: 2026-03-06

## Q2 - 重要不紧急

## Q3 - 紧急不重要

## Q4 - 不紧急不重要
```

关键点：每条任务带 deadline、最后进展、最后更新日期。Heartbeat 巡逻会据此判断是否需要提醒。

### 三个定时任务

整个系统由三个触发器驱动：

| 触发器 | 时间 | 做什么 |
|--------|------|--------|
| Heartbeat | 每小时 10:00-01:00 | 检查 DDL 到期 → 提醒或 HEARTBEAT_OK |
| 晨间提醒 | 每天 11:00 | 发当日任务清单 |
| 日报 | 每天 21:00 | 三阶段审核，综合汇报 |

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

晨间提醒只读 DDL.md，不需要跨 Agent 通信。输出格式：

```
🌅 今日任务 YYYY-MM-DD

【Q1 重点】
- [今天到期或紧急的任务，附 deadline]

【Q2 进度】
- [重要不紧急任务的最新进展]

【提醒】
- [需要注意的事项，如有]
```

**日报（cron，每天 21:00）——三阶段审核制**

日报不是简单地读文件生成，而是走一个三阶段审核流程：

| 阶段 | 做什么 | 是否广播 |
|------|--------|----------|
| 1. 信息采集 | 向各 Agent 收集当日数据 | 不广播 |
| 2. 初稿审核 | 整合初稿，发回各 Agent 逐句确认 | 不广播 |
| 3. 发送 | 确认无误后广播最终日报 | 广播 |

为什么要三阶段？因为实践中发现，管家 Agent 的「理解整合」环节容易出错——把 A 的信息张冠李戴给 B，或者用过期的 memory 数据。三阶段确保每条信息都经过来源确认。

```bash
openclaw cron add \
  --name "晚间日报" \
  --cron "0 21 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "执行三阶段日报流程：1.向 minicat 和凌若采集信息 2.整合后发回确认 3.确认无误后广播" \
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

在 `HEARTBEAT.md` 里写巡逻逻辑，按优先级检查：

```markdown
## Heartbeat（每小时）

读 DDL.md，按以下优先级检查：

**检查 A：今天或明天到期的任务**
→ 立刻提醒

**检查 B：Q1 任务最后更新日期超过 2 天**
→ 拖延模式

**检查 C：Rose 超过 1 天未回应任何提醒**
→ 消失模式

**以上都没有** → 回复 HEARTBEAT_OK
```

## 提醒策略

两种情况特殊处理，而不是简单催 deadline：

**拖延模式（检查 B：Q1 超 2 天无进展）**

不说「你的 deadline 快到了」，而是给一个最小可执行步骤：

> 「论文 deadline 还有 5 天，今天只需要做一件事：写完第三章的提纲，30 分钟就够。」

**消失模式（检查 C：超 1 天不回应）**

升频到每天两次提醒，保持存在感但不施压。

## 用户操作：全口语

不需要填表、不需要打命令，直接说话。Agent（小蜜）负责解析并更新 DDL.md：

| 用户说的 | Agent 做的 |
|---------|-----------|
| "XX 完成了" | 从 DDL.md 删除，记入 `memory/YYYY-MM-DD.md` |
| "XX 做了 [具体内容]" | 更新 DDL.md 中的最后进展和日期 |
| "XX deadline 改到 YY" | 更新 DDL.md 中的日期 |
| "新任务：XX，deadline YY，Q1" | 添加到 DDL.md 对应象限 |
| "把 XX 移到 Q2" | 更改任务所在象限 |

Rose 只管说话，不需要维护任何格式。

## 记忆系统

完成的任务不是简单归档，而是进入一个两层记忆系统：

**Daily Memory（`memory/YYYY-MM-DD.md`）——流水账**

```markdown
# 2026-03-06

## 任务
- ✅ 完成：H1B 材料提交（13:00 PST）
- 🔄 进展：论文做了第三章提纲
- ➕ 新增：Browser Relay 调研

## 日报
- 发送时间：21:48 PST
- minicat：今天 7 篇/次
- Rose 状态：开心/精力充沛

## 跨 Agent 协调
- 问 minicat 今日发布情况，确认 7 篇已 push

## 其他
- Token 消耗：密集 sessions_send 约 1M tokens/天
```

**Long-term Memory（`MEMORY.md`）——精炼知识**

不是流水账，只放跨天仍然重要的信息：

- Rose 的长期状态趋势（"最近两周偏疲惫"这种跨天判断）
- 关键 context（人物关系、重要偏好）
- 系统层面的教训（token 消耗、流程 bug）
- 各 Agent 的能力边界和已知问题

每次 session 启动时，小蜜会读今天和昨天的 daily memory + 长期 MEMORY.md，重建上下文。

## 为什么用多 Agent？

这个系统运行着三个 Agent，各有分工：

| Agent | Emoji | 职责 | 和 DDL 系统的关系 |
|-------|-------|------|-------------------|
| 小蜜 | 🏠 | 管家/总监 | 运行 DDL 巡逻、晨间提醒、日报，维护任务文件 |
| minicat | 🐱 | 博客助手 | 日报时被采集当天博客活动数据 |
| 凌若 | 💜 | 闺蜜/Coach | 日报时被采集 Rose 当日状态标签 |

小蜜是系统的中枢——不写博客（minicat 的事），不聊心事（凌若的事），只做协调和执行。

这是 [[openclaw-multi-agent-tutorial]] 里讲的多 Agent 分工模式在实际场景里的应用。关键设计原则：

**Agent 通信透明化**

小蜜通过 `sessions_send` 和其他 Agent 通信后，必须把内容广播到 Telegram 群。Rose 随时可以问「你跟 minicat 说了什么」，答案完全透明。唯一例外：日报阶段 1-2 的内部协调不广播，因为来回确认太多，等最终版一次性发。

**隐私边界**

凌若和 Rose 的私密对话不该出现在任何输出里。小蜜读凌若的 memory 时只读第一行状态标签（如"开心/精力充沛"），不看具体内容。日报里对凌若部分也只写「Rose 状态：[标签]」。

**不替 Rose 做决定**

小蜜提供信息和建议，但选择是 Rose 的。不越权替其他 Agent 做决定，只协调和通知。

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
