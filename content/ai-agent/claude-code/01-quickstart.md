---
title: "Claude Code 初级功能：Slash Commands、Memory 与 Skills"
date: 2026-03-31
tags:
  - claude-code
  - agent
  - cli
lang: zh
english: claude-code-beginner-guide.en
---

## 为什么用 Claude Code

Claude Code 是 Anthropic 推出的命令行 AI 编程工具。它直接在终端里运行，没有花哨的 GUI，打开项目目录输入 `claude` 就能开始。它能读你的代码、改文件、跑命令，基本上是一个住在终端里的结对编程伙伴。

跟 IDE 插件不同，Claude Code 的设计哲学是"你说，它做"。不需要手动选文件、复制粘贴上下文，它自己会找需要的信息。这篇笔记记录三个初级但核心的功能：Slash Commands（快捷命令）、Memory（记忆系统）和 Skills（可复用能力）。掌握这三个，日常使用就够顺手了。

## Slash Commands：快捷命令深度指南

### 基本概念与触发方式

Slash Commands 是 Claude Code 内置的快捷操作，用 `/` 开头触发。在对话中输入 `/` 就能看到可用命令列表，按 Tab 可以自动补全。这些命令不是给 AI 的提示词，而是直接执行的系统操作。

在 Claude Code 对话中：

```
You: /
# 此时会弹出可用命令列表

You: /c  # 输入前几个字母
# 会筛选匹配的命令（比如 /clear, /compact, /cost）

You: /clear  # 按 Enter 执行
Claude: 对话已清空，重新开始
```

### 常用内置命令详解

**上下文管理类**

```bash
/clear         # 彻底清空对话，从零开始。适合开始新任务时
/compact       # 压缩对话历史，保留关键信息但减少 token
/context       # 查看当前上下文使用情况（Token 占用可视化）
/cost          # 显示当前会话的 token 用量和费用
```

`/clear` 和 `/compact` 的区别很重要。比如你跟 Claude 讨论了半个小时的项目问题，积累了很多对话。此时：

- 用 `/clear`：所有对话历史都删除，包括前面得出的结论
- 用 `/compact`：Claude 会把前面的对话总结成一份精简版本存着，后续对话仍然能参考这些信息，但占用更少 token

长对话快撑满上下文窗口时，`/compact` 比 `/clear` 更实用。

**模型与性能类**

```bash
/model         # 切换模型（Sonnet 4.6 vs Opus 4.6）
/effort        # 调整推理强度（低/中/高/最高）
/fast          # 切换快速模式（权衡速度和准确性）
```

`/model` 很常用。Sonnet 4.6 速度快适合日常任务，Opus 4.6 更强适合复杂推理。可以根据任务复杂度动态切换。`/effort max` 会使用扩展推理（extended thinking），对付特别难的问题时有帮助。

**项目与会话管理类**

```bash
/init          # 初始化项目 CLAUDE.md
/memory        # 编辑 Memory 文件
/rename [name] # 给当前会话起个名字（方便后续 /resume）
/resume        # 恢复之前的会话
/branch        # 分支当前对话，在不同角度探索
```

`/rename` 很实用。默认会话名是创建时间，看不出是什么任务。如果你 `/rename auth-refactor`，之后就能用 `claude -r auth-refactor` 快速继续这个工作。

**代码与工作流类**

```bash
/diff          # 查看未提交的代码变更（交互式 diff）
/rewind        # 回到之前的某个时刻，重新尝试不同方案
/commit        # 让 Claude 帮你写 commit message 并提交
/pr            # 创建 Pull Request
```

`/diff` 是个隐藏宝藏。不用手动 `git diff` 再复制粘贴，直接看修改内容，甚至可以在里面标注疑问。

`/rewind` 用于实验：尝试了一个实现方案，觉得不满意，可以回到决策点重新尝试另一个方案，保留代码和对话记录。

### 命令的参数和组合

很多命令支持参数。比如：

```bash
/compact 请保留关于认证系统的所有信息
# Claude 会优先保留跟认证相关的内容

/rename api-refactor-session
# 会话名改为 "api-refactor-session"

/code-review src/auth.ts --strict
# 如果有 code-review skill，参数会被传递给它
```

参数通过空格分隔，如果参数含有空格，用引号：

```bash
/commit "fix: add two-factor auth validation"
```

### 实际使用场景示例

**场景 1：长期项目中途休息**

```
You: /rename feature-payment-integration
Claude: 会话已重命名为 "feature-payment-integration"

# 一小时后，想继续这个工作
You: claude -r feature-payment-integration
Claude: 恢复了之前的对话上下文
```

**场景 2：对话变得很长，需要整理**

```
You: /context
Claude: 显示上下文占用：[█████████░░░░] 67% (1.2M tokens)

You: /compact 保留所有关于数据库 schema 的讨论
Claude: 对话已压缩，释放了 300k tokens 空间，保留了 schema 相关内容
```

**场景 3：尝试多个方案**

```
You: 我需要重构这个认证系统
Claude: [提出方案 A]

You: 等等，我想试试方案 B 的思路
Claude: [给出方案 B]

You: /rewind
# 回到决策点，可以重新选择方案或看两个方案的对比
```

### 命令发现与帮助

不记得具体命令名？可以问 Claude 或查看帮助：

```bash
/help          # 显示所有可用命令和简短说明
```

或者直接问：

```
You: 我想看看现在的 token 用量
Claude: 你可以用 /cost 查看当前会话的费用和 token 使用情况
```

### 与自定义命令的关系

之前 Claude Code 支持在 `.claude/commands/` 目录创建自定义 Slash Commands。这个功能现在已合并到了 **Skills** 系统中（后面会讲）。

旧语法仍然兼容，但新建议都用 Skills。如果你看到 `.claude/commands/` 相关文档，知道它现在的推荐做法是迁移到 Skills 就行。

## Memory：跨会话的持久化上下文

### CLAUDE.md 是什么

每次启动新会话，Claude Code 默认不记得之前聊过什么。Memory 系统解决这个问题——它通过 `CLAUDE.md` 文件让 Claude 在每次启动时自动加载预设的上下文信息。你可以把它理解为给 Claude 的"备忘录"，写在里面的内容每次都会被读取。

### 三层 Memory 系统

CLAUDE.md 有一个分层设计，从通用到具体：

| 层级 | 文件位置 | 作用范围 |
|------|---------|---------|
| 用户级 | `~/.claude/CLAUDE.md` | 所有项目通用的偏好 |
| 项目级 | `项目根目录/CLAUDE.md` | 当前项目的规范和上下文 |
| 目录级 | `子目录/CLAUDE.md` | 特定目录的额外说明 |

用户级适合放通用偏好，比如"代码注释用英文""commit message 用 conventional commits 格式"。项目级放项目特定的信息，比如技术栈、架构决策、代码规范。目录级比较少用，但在 monorepo 里给不同子项目写各自的说明很方便。

三层 Memory 会自动合并。Claude Code 启动时先读用户级，再读项目级，最后读当前工作目录的目录级。如果有冲突，更具体的层级优先。

### 快速更新 Memory

除了直接编辑文件，Claude Code 提供了两种快速更新方式。第一种是在对话中用 `#` 前缀：

```
# 这个项目用 pnpm，不要用 npm
```

以 `#` 开头的内容会被 Claude 自动追加到 CLAUDE.md 里，不需要手动打开文件编辑。适合在工作过程中随手记录发现的规范或约定。

第二种是用 `/memory` 命令，它会直接打开 CLAUDE.md 让你编辑。适合需要整理、删改已有内容的时候。

### 导入其他文件

CLAUDE.md 支持用 `@` 语法导入其他文件的内容：

```markdown
@docs/architecture.md
@.cursor/rules
```

这样可以复用已有的文档，不需要把所有内容都塞进一个 CLAUDE.md 里。比如项目本来就有架构文档，直接引用就好。

### 自动 Memory

Claude Code 还有一个"自动 Memory"特性。当它在工作过程中发现了重要的项目信息（比如发现项目用了特殊的构建流程），会主动提议把这些信息写入 CLAUDE.md。你确认后它就会自动更新。这样 Memory 会随着使用越来越完善，不需要一开始就写得很全。

## Skills：可复用的能力模块

### 什么是 Skills

Skills 是 Claude Code 的能力扩展系统。一个 Skill 本质上是一个 Markdown 文件（通常叫 `SKILL.md`），里面描述了一种特定任务的执行方式——包括步骤、规范、可用的工具、注意事项等。你可以把 Skills 理解成"可复用的专家指南"。

比如你可以有一个"写博客"的 Skill，里面定义了 frontmatter 格式、文件命名规范、目录结构、写作风格要求。每次需要写博客时，Claude 加载这个 Skill 就知道该怎么做，不需要重复说明。

### Skills vs 旧版自定义命令

之前提到的自定义 Slash Commands 已经合并到了 Skills 系统。主要区别：

- **旧版命令**：放在 `.claude/commands/` 目录，格式受限，只能定义简单的提示词模板
- **Skills**：更灵活，支持描述触发条件、引用外部文件、定义完整的工作流程

Skills 是自定义命令的超集。如果你之前用过自定义命令，迁移到 Skills 会获得更强的表达能力。

### 三级渐进加载

Skills 采用渐进式加载策略，不会一次性把所有 Skill 都塞进上下文：

1. **发现层**：Claude Code 启动时只加载所有 Skills 的名称和描述（很短），知道有哪些能力可用
2. **匹配层**：根据用户的请求，判断哪个 Skill 最相关
3. **加载层**：只读取匹配到的那个 Skill 的完整内容

这个设计很聪明。如果你有 20 个 Skills，每个几百行，全部加载会浪费大量上下文窗口。渐进加载保证了只在需要时才占用 token。

### 创建一个 Skill

一个最简单的 Skill 结构：

```
skills/
  my-skill/
    SKILL.md
```

`SKILL.md` 的典型内容：

```markdown
---
name: my-skill
description: 什么时候用这个 Skill，能做什么
---

# My Skill

## 触发条件
当用户要求 XXX 时使用此 Skill。

## 步骤
1. 先做什么
2. 再做什么
3. 最后做什么

## 规范
- 输出格式要求
- 命名约定
- 注意事项
```

Skills 的注册方式取决于你使用的具体平台或框架。在 Claude Code 原生环境中，Skills 通常通过 CLAUDE.md 中的配置或特定的目录约定来发现和加载。

### 实际使用场景

几个典型的 Skill 用例：

- **代码审查**：定义审查的关注点、输出格式、严重程度分级
- **博客写作**：定义文章结构、frontmatter 格式、风格要求
- **项目初始化**：定义脚手架模板、依赖安装、配置生成流程
- **测试生成**：定义测试框架偏好、覆盖率要求、mock 策略

Skills 的价值在于把反复执行的任务标准化。一次定义，每次执行都保持一致。

## 初级学习路线

如果你刚开始用 Claude Code，建议按这个顺序上手：

**第一步**：安装并在一个小项目里运行 `claude`，用 `/init` 生成初始 CLAUDE.md，体验基本对话。

**第二步**：熟悉常用 Slash Commands，特别是 `/clear`、`/compact`、`/cost`。养成用 `/compact` 管理上下文的习惯。

**第三步**：手动编辑 CLAUDE.md，加入你的编码偏好和项目规范。观察 Claude 的行为是否符合你的预期。

**第四步**：当你发现某个任务反复执行时，把它抽象成一个 Skill。从简单的开始，逐步完善。

Claude Code 的进阶功能还有很多——Hooks（生命周期钩子）、MCP Server 集成、多模型切换策略等。但上面这三个基础功能用熟了，日常开发已经能覆盖大部分场景。

## 参考链接

- [Claude Code 官方文档](https://code.claude.com/docs/en/overview)
- [Slash Commands 完全参考](https://code.claude.com/docs/en/interactive-mode)
- [Claude Code Memory 文档](https://code.claude.com/docs/en/memory)
- [claude-howto 学习指南](https://github.com/luongnv89/claude-howto)
