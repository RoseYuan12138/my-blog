---
title: "Claude Code 中级功能：Subagents、MCP 和 Hooks"
date: 2026-03-31
tags:
  - claude-code
  - agent
  - mcp
  - hooks
lang: zh
---

用了一段时间 Claude Code 之后，基础的对话、编辑文件、跑命令已经很熟了。但真正让它从"聪明的补全工具"变成"能干活的 Agent"的，是三个中级功能：Subagents、MCP 和 Hooks。这篇笔记把这三个功能的核心概念和使用方式整理一遍。

## Subagents：把大任务拆给专门的助手

### 为什么需要 Subagents

Claude Code 运行时有上下文窗口的限制。当你让它同时处理多个复杂任务——比如一边重构后端 API，一边写前端组件——上下文会迅速膨胀，导致响应质量下降。Subagents 的思路很简单：把任务委派给独立的子 Agent，每个子 Agent 有自己的上下文窗口，专注做一件事。这就像你不会让一个人同时写代码和做 code review，而是分给两个人各干各的。

### Subagent 的配置格式

自定义 Subagent 是一个 Markdown 文件，放在项目的 `.claude/agents/` 目录下。文件用 YAML frontmatter 定义配置，正文就是给这个 Agent 的 system prompt。一个典型的 Subagent 文件长这样：

```yaml
---
name: reviewer
description: "专门做代码审查的 Agent"
tools:
  - Read
  - Grep
  - Glob
---

你是一个代码审查专家。检查代码中的 bug、性能问题和风格不一致。
给出具体的改进建议，引用具体的行号。
```

`name` 是调用时的标识，`description` 帮助 Claude 判断什么时候该委派给它，`tools` 限定了它能用的工具集。通过限制工具，你可以确保审查 Agent 只读代码不改代码，符合最小权限原则。

### 内置 Subagents

Claude Code 自带几个内置 Subagent。**Explore** 专门用来探索代码库结构，它会在独立上下文中扫描目录、读文件、搞清楚项目的架构，然后把结论带回来。**Plan** 则负责制定执行计划，它会分析需求、拆分步骤，输出一个结构化的行动方案。还有一个通用的 Subagent，用于处理不需要特殊配置的简单委派任务。

### 使用方式

调用 Subagent 有两种方式。一种是显式调用，直接在对话中指定：

```
用 reviewer agent 检查一下 src/api/auth.ts
```

另一种是自动委派——当你的 Subagent 描述写得够清晰，Claude 会根据任务内容自动判断是否需要委派。比如你说"检查这个 PR 的代码质量"，它会自动把任务交给 reviewer subagent。

### 后台运行和 Worktree 隔离

两个进阶用法值得注意。第一个是 `background: true`，让 Subagent 在后台运行，主 Agent 可以继续处理其他事情，不用等它完成。这对耗时较长的任务特别有用，比如全量代码扫描。

```yaml
---
name: scanner
description: "全量安全扫描"
background: true
tools:
  - Read
  - Grep
  - Glob
  - Bash
---
```

第二个是 `isolation: worktree`，它会为 Subagent 创建一个独立的 Git worktree。这意味着 Subagent 的文件修改不会影响主分支，适合做探索性的重构或者并行开发多个特性分支。完成后你可以选择合并或丢弃。

## MCP：让 Claude Code 连接外部世界

### MCP 是什么

Model Context Protocol（MCP）是一个开放协议，让 AI 模型能够和外部工具、数据源交互。你可以把它理解成 Claude Code 的"USB 接口"——通过标准化的协议，接入各种外部服务。MCP 定义了三种核心能力：**Tools**（让模型调用外部函数）、**Resources**（让模型读取外部数据）、和 **Prompts**（预定义的交互模板）。

### 实际应用场景

MCP 的强大之处在于它能接入的服务范围非常广。通过 GitHub MCP Server，Claude Code 可以直接创建 PR、查看 issue、合并分支。通过数据库 MCP Server（比如 Postgres MCP），它可以查询数据库、分析数据。还有 Google Docs、Slack、Linear 等各种服务的 MCP Server。社区已经构建了大量现成的 MCP Server，大部分可以直接拿来用。

### 配置方式

MCP Server 的配置写在 `.claude/settings.json` 或用户级别的配置文件中。支持两种主要的传输方式。**Stdio** 方式是在本地启动一个进程，通过标准输入输出通信：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxx"
      }
    }
  }
}
```

**HTTP** 方式则连接远程服务：

```json
{
  "mcpServers": {
    "remote-service": {
      "url": "https://mcp.example.com/mcp"
    }
  }
}
```

Stdio 适合本地工具，HTTP 适合远程服务。对于需要认证的远程 MCP Server，Claude Code 支持 OAuth 2.0 流程——首次连接时会引导你完成授权，之后自动管理 token 刷新。

### 典型工作流

一个使用 MCP 的典型工作流是这样的：你让 Claude Code 帮你处理一个 GitHub issue。它先通过 GitHub MCP 读取 issue 详情，分析问题，修改代码，然后直接创建 PR 并关联 issue。整个过程你不需要切到浏览器或者手动跑 `gh` 命令。

### MCP vs Memory

一个常见的困惑是 MCP 和 Claude Code 的 Memory 功能有什么区别。简单说：**Memory 是给 Claude 存储项目知识的**（比如代码规范、架构决策），内容存在 `CLAUDE.md` 文件里，每次启动时自动加载。**MCP 是给 Claude 连接外部服务的**，提供实时的工具调用能力。Memory 是静态的上下文注入，MCP 是动态的能力扩展。

## Hooks：事件驱动的自动化

### Hooks 的核心理念

Hooks 的思路很直白：在 Claude Code 做某个动作的前后、或者在某个特定时刻，自动执行你预设的 shell 命令或脚本。不需要 Claude 主动决定，而是由事件触发、确定性地执行。这和 Git hooks 的思路完全一样——commit 前自动跑 lint，push 前自动跑测试。

### 三个核心 Hook 事件

绝大多数情况下，你只需要关心这三个事件：

| 事件 | 何时触发 | 用途 |
|------|---------|------|
| **PreToolUse** | Claude 调用工具前 | 拦截危险操作、检查内容 |
| **PostToolUse** | Claude 调用工具后 | 自动处理、格式化、测试 |
| **Stop** | Claude 准备停止回复时 | 最后验证、自动提交 |

### 实际例子 1：自动格式化（最常用）

你要求 Claude 改代码，它改完后自动跑 Prettier 格式化。配置：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hook": {
          "type": "command",
          "command": "npx prettier --write $CLAUDE_FILE_PATH 2>/dev/null || true"
        }
      }
    ]
  }
}
```

**怎么用**：把这段 JSON 放在项目根目录的 `.claude/settings.json` 里（没有的话新建一个）。然后：

```
You: 把 src/main.ts 改成用 async/await
Claude: [改完文件]
[Hook 自动触发] npx prettier --write src/main.ts
[文件自动格式化完成]
```

**好处**：不用自己跑 `prettier`，改完就自动格式化，代码整洁。

### 实际例子 2：改文件前检查敏感信息

防止 Claude 把 API Key 或密码硬编码到代码里：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hook": {
          "type": "command",
          "command": "sh -c 'if grep -iE \"(api.?key|password|secret|token)\\s*=\\s*[\\\"\\']\" <<< \"$CLAUDE_TOOL_INPUT\" > /dev/null; then echo \"ERROR: 检测到硬编码的敏感信息!\" >&2; exit 2; fi; exit 0'"
        }
      }
    ]
  }
}
```

**怎么用**：同样放在 `.claude/settings.json`。然后：

```
You: 在 config.ts 里添加 API 密钥初始化
Claude: [开始写文件，包含硬编码的 API_KEY]
[Hook 触发检查]
ERROR: 检测到硬编码的敏感信息!
Claude: 我不能硬编码敏感信息。应该从环境变量读取...
[提出安全的方案]
```

**好处**：自动拦截不安全的代码，避免泄露。

### 实际例子 3：改完代码自动跑测试

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hook": {
          "type": "command",
          "command": "cd $CLAUDE_PROJECT_DIR && npm test -- --testPathPattern=$(basename $CLAUDE_FILE_PATH .ts) 2>&1 | head -50"
        }
      }
    ]
  }
}
```

**怎么用**：同样放在 `.claude/settings.json`。然后：

```
You: 修复 LoginForm 组件的 bug
Claude: [改了 LoginForm.tsx]
[Hook 自动触发] npm test -- --testPathPattern=LoginForm
[测试结果输出到 Claude]
Claude: 看到了，有 2 个测试失败...我来修复
[继续修改代码直到测试通过]
```

**好处**：改完代码立刻跑测试，Claude 能看到结果，继续修复。不用你手动跑测试、复制粘贴错误日志。闭环自动化。

### 实际例子 4：自动提交

在 Claude 停止时，自动提交所有改动：

```json
{
  "hooks": {
    "Stop": [
      {
        "hook": {
          "type": "command",
          "command": "cd $CLAUDE_PROJECT_DIR && git add -A && git commit -m 'chore: auto-commit by Claude Code' 2>/dev/null || true"
        }
      }
    ]
  }
}
```

**怎么用**：

```
You: 给 UserService 添加 getById 方法
Claude: [修改代码，完成任务]
[Claude 准备停止]
[Hook 触发] git add -A && git commit...
[改动自动提交到 Git]
```

**好处**：不用手动 `git add` 和 `git commit`。

---

## 三个功能怎么协作

这三个功能并不是孤立的，它们组合起来才是完整的 Agent 架构。一个实际的场景：你让 Claude Code 处理一批 GitHub issues。**MCP** 连接 GitHub 拉取 issue 列表；主 Agent 分析后，用 **Subagents** 并行处理多个 issue，每个 Subagent 在独立的 worktree 里修改代码；**Hooks** 在每个修改后自动跑测试和格式化，确保代码质量。最后主 Agent 汇总结果，通过 MCP 创建 PR。

## 学习建议

先从 Hooks 开始，因为它最简单也最实用——复制一个自动格式化的 Hook，立刻就能感受到省事的好处。然后尝试 MCP，接入一两个常用服务（比如 GitHub）。最后再玩 Subagents，在真正需要并行或隔离的场景下使用。不需要一口气全学会，用到哪个学哪个。

## 参考链接

- [Claude Code 官方文档](https://code.claude.com/docs/en)
- [Model Context Protocol 官方网站](https://modelcontextprotocol.io/)
- [MCP Servers 社区仓库](https://github.com/modelcontextprotocol/servers)
- [claude-howto 学习指南](https://github.com/luongnv89/claude-howto)
