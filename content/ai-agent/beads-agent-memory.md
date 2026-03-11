---
title: "Beads: Agent 的持久化内存系统"
date: 2026-03-11
tags:
  - AI Agent
  - 开发工具
  - 内存系统
lang: zh
---

> [English Version](beads-agent-memory.en.md)

## 核心问题：Agent 的"失忆症"

用过 Claude Code、Codex 或其他 coding agent 的人都遇到过同一个问题：**agent 没有跨 session 的记忆**。

每次对话窗口关闭或上下文被压缩（compaction），agent 就像《记忆碎片》（Memento）里的主角一样失忆了——它醒来后只能看到磁盘上留下的文件，然后靠猜来决定接下来做什么。

这在实际工程中是个大问题：

- 一个功能的实现通常要跨越多个 session（写代码 → 测试 → review → 修复 → 清理）
- 工作流经常嵌套——修 UI 组件时发现数据库有问题，先去修数据库，再回来
- 人类靠大脑里的全局画面来管理这种嵌套，但 agent 做不到

结果就是：agent 丢失上下文、重复做已经完成的工作、忘记原来的计划。

## Beads 是什么

[Beads](https://github.com/steveyegge/beads) 是 Steve Yegge 开发的一个 **coding agent 持久化内存系统**。核心思想很简单：给 agent 一个结构化的、跨 session 持久存在的"大脑"。

它本质上是一个 **分布式、git-backed 的图结构 issue tracker**，专门为 AI agent 设计。

安装和使用非常直接：

```bash
# 安装 beads CLI
curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash

# 在你的项目里初始化
cd your-project
bd init

# 告诉你的 agent 用它
echo "Use 'bd' for task tracking" >> AGENTS.md
```

就这样——agent 立刻获得一次"认知升级"（cognitive upgrade），能做长期规划和任务发现了。

## 背景故事

Steve Yegge 的开发经历本身就很有戏剧性。

他花了 40 天 40 夜疯狂 vibe coding（他的原话：在海滩上 coding、开车 60mph 时语音 coding、在商场里 coding），创建了一个叫 vibecoder 的项目——350k 行代码的 agent 编排引擎。

然后他发现了两个致命的架构错误：

1. **Temporal 太重了**：用 Temporal 做轻量级开发者工具，是杀鸡用牛刀
2. **Markdown 计划是个坑**：agent 默认用 markdown 文件做计划，但这些文件会迅速腐烂——他最终积累了 605 个 markdown 计划文件，混乱不堪

于是他把整个项目烧掉，从灰烬中诞生了 Beads。

## 关键设计

### 依赖感知的图结构

Beads 最核心的创新是用 **dependency-aware graph** 替代扁平的 markdown 计划。

传统方式：

```
plans/
├── plan-001-ui-component.md
├── plan-002-database-fix.md
├── plan-003-testing.md
└── ... (605 个类似的文件)
```

Beads 方式：

```
bd-a3f8        (Epic)
├── bd-a3f8.1  (Task: UI 组件)
│   └── bd-a3f8.1.1  (Sub-task: 样式调整)
└── bd-a3f8.2  (Task: 数据库修复，blocks bd-a3f8.1)
```

任务之间有明确的依赖关系（blocks、relates_to、duplicates、supersedes），agent 可以通过 `bd ready` 查看当前没有阻塞的任务，直接开工。

### Dolt 驱动的版本控制

Beads 底层用的是 [Dolt](https://github.com/dolthub/dolt)——一个版本控制的 SQL 数据库。这意味着：

- **Cell 级别的 merge**：不像 git 的文件级冲突，Dolt 可以精确到单元格
- **原生分支**：多个 agent 可以在不同分支上并行工作
- **内置 sync**：通过 Dolt remote 同步

### Hash-based ID

每个任务的 ID 是 hash 生成的（如 `bd-a1b2`），这巧妙地避免了多 agent 或多分支场景下的 ID 冲突问题。

### 记忆衰减（Compaction）

旧的已关闭任务会被语义压缩（semantic summarization），节省上下文窗口。就像人类的记忆一样——细节慢慢淡去，但关键信息保留。

### 消息系统

Beads 内置了消息类型的 issue，支持线程（`--thread`）、临时生命周期和邮件委派。这让多 agent 之间的通信也有了持久化的载体。

## 核心命令

| 命令 | 作用 |
|------|------|
| `bd ready` | 列出所有没有阻塞的任务 |
| `bd create "Title" -p 0` | 创建一个 P0 任务 |
| `bd update <id> --claim` | 原子性地认领一个任务 |
| `bd dep add <child> <parent>` | 添加任务依赖关系 |
| `bd show <id>` | 查看任务详情和审计轨迹 |

## 对比：传统方案 vs Beads

| 维度 | Markdown 计划 | AGENTS.md / CLAUDE.md | Beads |
|------|--------------|----------------------|-------|
| 持久性 | 文件留在磁盘上，但内容混乱 | 每次 session 手动维护 | 结构化存储，自动持久化 |
| 依赖管理 | 无 | 无 | 原生支持 |
| 多 agent 协作 | 冲突频繁 | 不支持 | Hash ID + Dolt merge |
| 上下文效率 | 605 个文件全加载？ | 单文件，容易过长 | 按需查询 + 记忆衰减 |
| 任务发现 | agent 自己猜 | agent 自己猜 | `bd ready` 自动告诉你 |

## 应用场景

- **长周期开发任务**：跨越多天、多个 session 的功能开发，agent 不会忘记进度
- **多 agent 协作**：多个 agent 在不同分支上工作，通过 Beads 共享任务状态
- **开源贡献**：`bd init --contributor` 把计划 issue 路由到独立 repo，不污染 PR
- **个人隐身模式**：`bd init --stealth` 在共享项目中使用 Beads 而不提交文件

支持的 coding agent 包括 Claude Code、Sourcegraph Amp、OpenAI Codex、GitHub Copilot 等。

## 安装方式

```bash
# npm
npm install -g @beads/bd

# Homebrew
brew install beads

# Go
go install github.com/steveyegge/beads/cmd/bd@latest

# 一键脚本
curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
```

支持 macOS、Linux、Windows、FreeBSD。

## 我的思考

Beads 解决的问题很真实。我自己在用 agent 系统时，最痛苦的就是上下文丢失——一个 session 里讲好的计划，下个 session 就得重新交代一遍。

有几点值得关注：

1. **Graph 思维 vs 线性思维**：用依赖图来管理任务，比线性的 TODO 列表强太多。人类的工作本来就是图结构的。
2. **让 agent 自己发现工作**：`bd ready` 这个设计很聪明——agent 不需要人类告诉它"接下来做什么"，它自己就能找到。
3. **记忆衰减**：这个概念很优雅，模拟了人类记忆的工作方式。不是所有信息都值得永远保留。

当然也有一些需要观察的：
- Dolt 作为依赖是否会增加复杂度
- 对于小项目是否有些过重
- 社区生态（目前 GitHub 18.7k+ stars，势头不错）

总的来说，如果你在做比 "hello world" 复杂一点的 vibe coding，Beads 值得试试。

## 参考链接

- [GitHub: steveyegge/beads](https://github.com/steveyegge/beads)
- [Steve Yegge: Introducing Beads: A coding agent memory system (Medium)](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a)
- [Dolt: 版本控制的 SQL 数据库](https://github.com/dolthub/dolt)
- [Beads 安装指南](https://github.com/steveyegge/beads/blob/main/docs/INSTALLING.md)
- [Agent 工作流指南](https://github.com/steveyegge/beads/blob/main/AGENT_INSTRUCTIONS.md)
- [社区工具列表](https://github.com/steveyegge/beads/blob/main/docs/COMMUNITY_TOOLS.md)
