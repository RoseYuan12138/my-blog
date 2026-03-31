---
title: "Claude Code 高级功能：Plugins、Planning Mode 与 Extended Thinking"
date: 2026-03-31
tags:
  - claude-code
  - agent
  - dev-tools
lang: zh
---

用 Claude Code 写代码，基础功能已经够强了——读文件、改代码、跑命令，日常开发绑绑有余。但碰到复杂场景，比如要把一套工作流分享给团队、要重构一个大项目、要做架构级别的决策，基础功能就有点力不从心了。这篇笔记整理三个高级功能：Plugins、Planning Mode 和 Extended Thinking，它们分别解决"打包复用"、"先想后做"和"深度推理"的问题。

## Plugins：把工具包打包成一个整体

### 什么是 Plugin

Claude Code 的 Plugin 不是单个工具，而是一个**完整方案的打包**。想象你为某个特定工作流配了一堆东西：几个 MCP server 提供外部能力，一些 Hook 做自动化触发，一个 SKILL 文件定义行为规范，可能还有 Subagent 配置。这些零散的配置组合在一起才能完成一个任务，而 Plugin 就是把它们打包成一个可安装、可分享的单元。

举个例子：你搭了一套"代码审查助手"，包含连接 GitHub API 的 MCP server、提交前自动 lint 的 Hook、审查流程的 SKILL 指引。与其让别人手动配这一堆东西，不如打包成一个 Plugin，一条命令装好。

### Plugin 的结构

一个 Plugin 本质上是以下组件的任意组合：

- **SKILL 文件**：定义 agent 的行为规范和知识，告诉 Claude 该怎么做
- **Subagent 配置**：为特定子任务配置专门的 agent
- **MCP Server**：提供外部工具和数据源的连接
- **Hooks**：在特定事件（如文件保存、命令执行前后）触发的自动化脚本

不是每个组件都必须有，按需组合就行。一个简单的 Plugin 可能只有一个 SKILL 加一个 MCP server，复杂的可能全都用上。

### 常用命令

Plugin 的管理通过内置斜杠命令完成：

```bash
# 安装一个 plugin（从 registry 或本地路径）
/plugin install <name-or-path>

# 查看已安装的 plugins
/plugin list

# 启用 / 禁用某个 plugin（不卸载，只是开关）
/plugin enable <name>
/plugin disable <name>

# 彻底卸载
/plugin uninstall <name>
```

`enable` 和 `disable` 很实用——有些 Plugin 你不是每天都用，禁用后不占上下文，需要时再打开。

### 发布和分享

写好的 Plugin 可以发布到 Plugin registry 供别人安装。发布前确保结构清晰、README 写明白用途和依赖。团队内部也可以通过本地路径或 Git 仓库直接安装，不一定非要走公共 registry。

### 什么时候该创建 Plugin

不是所有配置都值得打包成 Plugin。判断标准很简单：**如果你发现自己在不同项目里重复配置同一套东西，或者想把一个工作流分享给别人，那就该建 Plugin 了。** 单个项目的一次性配置直接放项目的 `.claude/` 目录就够了，别过度工程化。

## Planning Mode：先想清楚再动手

### 什么是 Planning Mode

Planning Mode 是一个**两阶段工作流**：第一阶段 Claude 只做计划——分析需求、拆解步骤、列出要改的文件和改动思路；第二阶段你确认后它才开始执行。这和默认模式的区别在于，默认模式下 Claude 会边想边做，Planning Mode 则强制把"想"和"做"分开。

### 怎么激活

两种方式：

```bash
# 方式一：在对话中用斜杠命令切换
/plan

# 方式二：启动时指定权限模式
claude --permission-mode plan
```

用 `/plan` 命令可以在对话中随时切入计划模式，适合临时需要谨慎处理的任务。`--permission-mode plan` 则是整个会话都以计划模式运行，适合一开始就知道任务比较复杂的情况。

### 为什么要用

一个字：**把控力**。默认模式下 Claude 可能改着改着就跑偏了，改了你不想改的文件，或者选了一个不理想的实现路径。Planning Mode 让你在执行前就能看到完整计划，及时纠偏。这在几种场景下特别有价值：

- **大规模重构**：涉及几十个文件的改动，你需要先确认改动范围和顺序
- **新特性开发**：架构选型、接口设计这些决策应该在写代码之前敲定
- **架构改动**：比如换数据库、改微服务边界，影响面大，得想清楚

### 计划的修改和确认

Claude 给出计划后，你不是只能"同意"或"拒绝"。你可以**直接在对话里提修改意见**：调整步骤顺序、删掉某些改动、补充遗漏的点。Claude 会根据你的反馈更新计划，直到你明确 approve。这个来回讨论的过程本身就很有价值——它迫使你在动手之前把需求和方案想清楚。

## Extended Thinking：让 Claude 深度思考

### 什么是 Extended Thinking

Extended Thinking 让 Claude 在回答之前进行**多步骤的内部推理**。正常模式下 Claude 的回答是"看到问题就开始写"，Extended Thinking 则给它一个专门的推理空间，可以在里面分析问题、权衡方案、检查逻辑，然后再给出最终答案。你可以把它理解为让 Claude 先在草稿纸上演算一遍。

### 怎么激活

```bash
# 方式一：快捷键（在 CLI 交互界面中）
Alt + T

# 方式二：斜杠命令调整 effort 级别
/effort high
```

`Alt+T` 是快速切换开关，`/effort` 命令可以更精细地控制推理深度。

### Effort 级别

Extended Thinking 提供四个级别：

| 级别 | 适用场景 | 推理深度 |
|------|---------|---------|
| `low` | 简单问题，快速回答 | 最少推理 |
| `medium` | 一般开发任务 | 适度推理 |
| `high` | 复杂逻辑、架构设计 | 深度推理 |
| `max` | 最复杂的问题 | 最大推理深度 |

默认是不开启的。大部分日常任务不需要 Extended Thinking，开了反而慢。

### 什么时候该用

Extended Thinking 真正发挥作用的场景是那些**需要全局考虑的复杂问题**：

- **架构决策**：选技术栈、设计系统边界、定数据模型——这些决策需要综合考虑多个维度
- **复杂 bug 分析**：bug 的表现和根因隔了好几层调用，需要系统性地排查
- **算法设计**：涉及正确性证明、边界条件分析、性能评估的场景
- **代码审查**：需要理解大量上下文才能判断改动是否合理

### 成本和效果的权衡

Extended Thinking 会消耗更多 token，响应时间也更长。`max` 级别的一次回答可能花掉正常回答好几倍的 token。所以不要无脑开最高级别——简单问题用 `low` 甚至不开，复杂问题再上 `high` 或 `max`。根据任务复杂度动态调整才是正确用法。

## 三个功能怎么配合

这三个功能不是孤立的，实际使用中经常组合：

**Planning Mode + Extended Thinking** 是最常见的组合。面对复杂重构任务，先开 Extended Thinking 让 Claude 深度分析现有代码和改动影响，再用 Planning Mode 输出结构化的执行计划。这样计划的质量会明显提升。

**Plugins + Planning Mode** 适合团队协作。把团队的标准开发流程封装成 Plugin（包含代码规范 SKILL、CI Hook 等），再配合 Planning Mode 确保每次改动都经过审核。

实际建议是：**日常开发用默认模式就够了**，别把简单事情复杂化。碰到大任务先切 Planning Mode 理清思路，遇到难题开 Extended Thinking 深入分析，有了成熟的工作流就打包成 Plugin。循序渐进，按需使用。

## 参考链接

- [Claude Code 官方文档](https://code.claude.com/docs/en)
- [Plugins 教程](https://github.com/luongnv89/claude-howto)
- [claude-howto 学习指南](https://github.com/luongnv89/claude-howto)
