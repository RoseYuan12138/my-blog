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

### Plugin 的目录结构

一个 Plugin 本质上是以下组件的任意组合。先看一个真实的代码审查 Plugin 的完整目录结构：

```text
code-review/
├── .claude-plugin/
│   └── plugin.json          # Plugin 元信息（必需）
├── skills/
│   └── code-review/
│       └── SKILL.md          # 审查流程的行为规范
├── agents/
│   ├── bug-detector.md       # 专找 bug 的子 Agent
│   ├── claude-md-compliance.md
│   ├── code-comments.md
│   ├── historical-context.md
│   └── pr-history.md
├── commands/
│   └── code-review.md        # /code-review 斜杠命令
├── hooks/
│   └── hooks.json            # 事件触发器配置
├── .mcp.json                 # MCP server 定义（可选）
└── README.md
```

不是每个组件都必须有，按需组合就行。一个简单的 Plugin 可能只有一个 SKILL 加一个 MCP server，复杂的可能全都用上。

### plugin.json：Plugin 的身份证

`plugin.json` 放在 `.claude-plugin/` 目录下，定义 Plugin 的基本信息：

```json
{
  "name": "code-review",
  "version": "1.0.0",
  "description": "Automated PR code review using multiple specialized agents with confidence-based scoring",
  "author": "anthropic"
}
```

就这么简单。名字、版本、描述、作者。Claude Code 靠这个文件识别和管理 Plugin。

### SKILL.md：告诉 Claude 该怎么做

SKILL.md 是 Plugin 的"行为手册"，定义了 Claude 在这个场景下应该遵循的流程和规范。以代码审查 Plugin 为例：

```markdown
# Code Review Skill

## Trigger
当用户请求代码审查或执行 /code-review 命令时激活。

## Workflow
1. 确定要审查的 PR 或 diff 范围
2. 并行启动 5 个专门的审查 Agent：
   - bug-detector：检查潜在 bug 和逻辑错误
   - claude-md-compliance：检查是否符合项目 CLAUDE.md 规范
   - code-comments：评估注释质量和代码可读性
   - historical-context：对比历史改动，检查是否引入回归
   - pr-history：分析 PR 历史，给出上下文建议
3. 收集所有 Agent 的发现，按置信度评分过滤误报
4. 生成结构化的审查报告

## Rules
- 置信度低于 70% 的 issue 标记为 "suggestion" 而非 "problem"
- 不要在审查中做任何代码修改
- 发现安全问题时置信度自动提升到 90%+
```

### hooks.json：自动化触发器

hooks.json 定义了在特定事件发生时自动执行的脚本。比如一个安全检查 Plugin 的 hooks：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/security-check.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format-code.sh"
          }
        ]
      }
    ]
  }
}
```

这里 `PreToolUse` 表示在 Claude 写文件之前触发安全检查，`PostToolUse` 表示写完后自动格式化。`matcher` 用正则匹配工具名，`${CLAUDE_PLUGIN_ROOT}` 会自动替换为 Plugin 的安装路径。

常用的 Hook 事件包括：`SessionStart`（会话开始）、`PreToolUse`/`PostToolUse`（工具调用前后）、`Stop`（Claude 完成回答时）、`SubagentStart`/`SubagentStop`（子 Agent 启停时）。

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

### 官方 Plugin 示例

Anthropic 在 [claude-code 仓库](https://github.com/anthropics/claude-code/tree/main/plugins) 里提供了一批官方 Plugin，可以直接用或当模板参考：

| Plugin | 功能 |
|--------|------|
| `code-review` | 5 个并行 Agent 做 PR 审查 |
| `feature-dev` | 7 阶段结构化特性开发流程 |
| `security-guidance` | 写文件时自动检查 9 种安全模式 |
| `commit-commands` | `/commit`、`/commit-push-pr` 等 Git 快捷操作 |
| `plugin-dev` | Plugin 开发工具包，含 7 个专家 Skill |

### 什么时候该创建 Plugin

不是所有配置都值得打包成 Plugin。判断标准很简单：**如果你发现自己在不同项目里重复配置同一套东西，或者想把一个工作流分享给别人，那就该建 Plugin 了。** 单个项目的一次性配置直接放项目的 `.claude/` 目录就够了，别过度工程化。

## Planning Mode：先想清楚再动手

### 什么是 Planning Mode

Planning Mode 是一个**两阶段工作流**：第一阶段 Claude 只做计划——分析需求、拆解步骤、列出要改的文件和改动思路；第二阶段你确认后它才开始执行。这和默认模式的区别在于，默认模式下 Claude 会边想边做，Planning Mode 则强制把"想"和"做"分开。

在 Planning Mode 下，Claude 只有只读权限——它可以读文件、搜索代码、分析结构，但**不能**写文件或执行命令。这就保证了在你点头之前，代码库不会有任何改动。

### 怎么激活

```bash
# 方式一：对话中按 Shift+Tab 循环切换模式
# Normal Mode → Auto-Accept Mode → Plan Mode → Normal Mode
# 状态栏会显示 "⏸ plan mode on"

# 方式二：启动时指定
claude --permission-mode plan

# 方式三：headless 模式下使用
claude --permission-mode plan -p "分析这个项目的认证模块"
```

`Shift+Tab` 是最灵活的，在对话中随时切换。

### 默认模式 vs Planning Mode 的效果对比

同一个任务："重构 `src/auth/` 目录下的认证逻辑，把 session-based 改成 JWT"。

**默认模式的行为：**

```text
> 重构 src/auth/ 的认证逻辑，改成 JWT

Claude: 好的，我来看看现有代码...
[读取 src/auth/session.js]
[读取 src/auth/middleware.js]

我会开始修改。先装 jsonwebtoken 包...
[执行 npm install jsonwebtoken]
[修改 src/auth/middleware.js - 替换 session 检查为 JWT 验证]
[修改 src/auth/login.js - 改为返回 JWT token]
[修改 src/routes/api.js - 更新中间件引用]
...
```

Claude 边分析边改，你能看到每一步的操作，但很难在它改到一半时喊停。

**Planning Mode 的行为：**

```text
> 重构 src/auth/ 的认证逻辑，改成 JWT

Claude: 我先分析一下现有的认证架构。
[读取 src/auth/ 下所有文件]
[搜索所有引用 session 的代码]
[分析 6 个测试文件的覆盖范围]

以下是我的重构计划：

## 改动范围
影响文件：12 个（4 个核心 + 8 个引用方）

## 执行步骤
1. 安装依赖：jsonwebtoken, @types/jsonwebtoken
2. 新建 src/auth/jwt.ts - JWT 签发和验证的工具函数
3. 修改 src/auth/middleware.ts - 替换 session 中间件为 JWT 中间件
4. 修改 src/auth/login.ts - 登录成功后返回 JWT 而非设置 session
5. 修改 src/auth/logout.ts - 改为客户端清除 token（可选：加入黑名单机制）
6. 更新 8 个引用文件中的 session 相关代码
7. 更新测试用例

## 需要确认的问题
- Token 过期时间设多久？（建议 access: 15min, refresh: 7d）
- 要不要加 refresh token 机制？
- 现有的 session store (Redis) 是否保留用于 token 黑名单？

要我开始执行这个计划吗？可以先调整。
```

区别一目了然：Planning Mode 让你在**一行代码都没改的情况下**看到完整的改动方案，还能在这个阶段讨论架构决策。

### 计划什么时候会被频繁修改

计划不是一次定稿的——以下情况预期会有多轮迭代：

- **需求本身不清晰**：Rose 说"优化一下性能"，但没说优化哪里、目标指标是什么。Claude 的第一版计划可能方向就不对
- **技术方案有不确定性**：比如不确定新版 API 是否向后兼容，计划可能在调研后大改
- **发现隐藏的依赖关系**：分析代码后发现改 A 必须同时改 B 和 C，计划范围扩大
- **约束条件变化**：原本计划停机迁移，后来说不能停机，方案推翻重来

### 一个计划→修改→执行的对话示例

```text
> [Plan Mode] 给 API 加上 rate limiting

Claude: 分析了现有的 Express 中间件结构。计划如下：
  1. 安装 express-rate-limit
  2. 在 src/middleware/rateLimit.ts 创建限流中间件
  3. 在 src/app.ts 全局注册
  预计影响 2 个文件，新建 1 个。

> 不要全局限流，按路由分别配置。/api/auth/* 要严格一些（10次/分钟），
> 其他 API 宽松一些（100次/分钟）。

Claude: 明白，更新计划：
  1. 安装 express-rate-limit
  2. 新建 src/middleware/rateLimit.ts - 导出两个预设：
     - strictLimit: 10 req/min（用于 auth 路由）
     - standardLimit: 100 req/min（用于其他 API）
  3. 修改 src/routes/auth.ts - 应用 strictLimit
  4. 修改 src/routes/api.ts - 应用 standardLimit
  5. 新建测试 tests/middleware/rateLimit.test.ts
  预计影响 3 个文件，新建 2 个。

> 好，执行吧。

[切换回 Normal Mode，Claude 按计划开始执行]
```

这个来回讨论的过程本身就很有价值——它迫使你在动手之前把需求和方案想清楚。

### 为什么要用

一个字：**把控力**。默认模式下 Claude 可能改着改着就跑偏了，改了你不想改的文件，或者选了一个不理想的实现路径。Planning Mode 在以下场景特别有价值：

- **大规模重构**：涉及几十个文件的改动，你需要先确认改动范围和顺序
- **新特性开发**：架构选型、接口设计这些决策应该在写代码之前敲定
- **代码探索**：想先深入了解代码库再决定怎么改
- **多步骤实现**：Feature 需要改很多文件，想先看全局规划

## Extended Thinking：让 Claude 深度思考

### 什么是 Extended Thinking

Extended Thinking 让 Claude 在回答之前进行**多步骤的内部推理**。正常模式下 Claude 的回答是"看到问题就开始写"，Extended Thinking 则给它一个专门的推理空间，可以在里面分析问题、权衡方案、检查逻辑，然后再给出最终答案。你可以把它理解为让 Claude 先在草稿纸上演算一遍。

推理过程默认不显示。想看的话，在 CLI 里按 `Ctrl+O` 打开 verbose 模式，就能看到 Claude 的思考过程。

### 怎么激活

```bash
# 方式一：快捷键（在 CLI 交互界面中）
Alt + T  # 快速开关

# 方式二：斜杠命令调整 effort 级别
/effort high
/effort max
```

### Effort 级别与判断标准

Extended Thinking 有四个级别。关键是知道什么任务该用什么级别：

| 级别 | 适用场景 | 推理深度 |
|------|---------|---------|
| `low` | "把这个变量名改成 camelCase"、"加个 console.log" | 几乎不推理，最快 |
| `medium` | "写个 React 组件"、"加个 API endpoint" | 常规推理，默认够用 |
| `high` | "这个并发 bug 怎么回事"、"设计 WebSocket 消息协议"、"重构这个模块的错误处理" | 深度推理，会系统性分析 |
| `max` | "从零设计微服务架构"、"这个分布式一致性问题怎么解"、"评审整个认证系统的安全性" | 最大推理深度，耗时最长 |

**简单判断规则：**
- 如果你能在脑子里想清楚怎么做 → `low` 或 `medium`
- 如果你自己也得画图、列 pros/cons 才能决定 → `high`
- 如果你自己想了半天还没把握 → `max`

### 推理输出长什么样

开启 verbose 模式后（`Ctrl+O`），你能看到 Claude 的推理过程。以"分析一个内存泄漏问题"为例，`/effort high` 的推理输出大概是这样的：

```text
[Thinking]
用户报告内存泄漏，发生在长时间运行后。让我分析可能的原因...

1. 先看 server.ts 的连接处理：
   - WebSocket 连接存在 `connections` Map 中
   - onClose 处理器有 try-catch 但 catch 是空的... 这是问题吗？
   
2. 检查 eventEmitter：
   - 每次连接都 addListener，但断开时没有 removeListener
   - 这会导致 listener 累积 → 经典的内存泄漏模式
   
3. 还要看 setInterval：
   - heartbeat 用了 setInterval 但断开时没有 clearInterval
   - 又一个泄漏源
   
结论：两个泄漏源——未清理的 event listener 和未清除的 interval。
先修 listener 问题因为影响更大。
[End Thinking]

我找到了两个内存泄漏的原因...
```

而 `/effort max` 的推理会更深入，可能还会分析整个 GC 行为、评估不同修复方案的风险、考虑是否需要加监控等。

### Token 成本估算

Extended Thinking 消耗的额外 token 是实打实的。粗略估计：

| 级别 | 推理 Token（大约） | 相对成本 | 响应时间 |
|------|-------------------|---------|---------|
| `low` | ~500 | 1x | 几秒 |
| `medium` | ~2,000 | 2-3x | 5-10 秒 |
| `high` | ~8,000 | 5-8x | 15-30 秒 |
| `max` | ~30,000+ | 15-30x | 30-90 秒 |

这些数字因任务复杂度差异很大，但数量级是对的。一个 `max` 级别的架构分析可能花掉几万个推理 token，成本是普通回答的 10-30 倍。所以不要无脑开最高级别——简单问题用 `low` 甚至不开，复杂问题再上 `high` 或 `max`。

### 什么时候该用

Extended Thinking 真正发挥作用的场景是那些**需要全局考虑的复杂问题**：

- **架构决策**：选技术栈、设计系统边界、定数据模型
- **复杂 bug 分析**：bug 的表现和根因隔了好几层调用
- **算法设计**：涉及正确性证明、边界条件分析、性能评估
- **代码审查**：需要理解大量上下文才能判断改动是否合理

## 三个功能怎么配合

这三个功能不是孤立的，实际使用中经常组合。

### 实战场景：重构 API 认证模块

假设你接到一个任务：把老项目的 API 认证从 API Key 直接校验改成 OAuth 2.0 + JWT 的方案。这个任务涉及架构变更、多文件改动、安全性考量，正好用上全部三个功能。

**第一步：开 Extended Thinking 分析现状**

```bash
/effort high
```

```text
> 分析 src/auth/ 目录下的认证实现，我想把它从 API Key 改成 OAuth 2.0 + JWT。
> 先别改，告诉我现在的架构和潜在风险。

[Thinking]
让我系统分析现有的认证架构...

当前结构：
- src/auth/apiKey.ts: 直接从 header 读 X-API-Key，查数据库比对
- src/auth/middleware.ts: 全局中间件，每个请求都查一次数据库
- src/models/apiKey.ts: Mongoose model，存 key + userId + permissions
- 引用方：src/routes/ 下 14 个路由文件都用了 requireAuth 中间件

问题：
1. 每请求查数据库 → 高延迟，数据库是瓶颈
2. API Key 没有过期机制 → 泄漏了就永久有效
3. 权限是粗粒度的 → 只有 read/write/admin 三级
4. 没有 rate limiting per key → 被滥用无法单独限制

迁移到 OAuth 2.0 + JWT 的关键决策点：
- Authorization server 自建还是用第三方（Auth0, Keycloak）？
- JWT 存什么 claim？权限模型要不要重新设计？
- 要不要保持向后兼容（同时支持旧 API Key 一段时间）？
- Refresh token 存哪里？Redis？数据库？

风险评估：
- 14 个路由文件都要改，中间件接口变化大
- 现有用户的迁移策略需要考虑
- JWT 无法撤销（除非加黑名单机制），和 API Key 的"删了就失效"不同
[End Thinking]

分析完成。现有认证架构有以下核心问题...
（输出完整分析报告）
```

有了 Extended Thinking 的深度分析，你对现状的理解就很充分了。

**第二步：切到 Planning Mode 制定方案**

```bash
# 按 Shift+Tab 切换到 Plan Mode（状态栏显示 ⏸ plan mode on）
/effort max  # 方案设计是最复杂的部分，开到最大
```

```text
> 基于刚才的分析，制定迁移计划。
> 约束：自建 auth server，保持 30 天向后兼容，用 Redis 存 refresh token。

Claude 的计划输出：

## OAuth 2.0 + JWT 迁移计划

### Phase 1: 基础设施（不影响现有功能）
1. 新建 src/auth/jwt/
   - tokenService.ts: JWT 签发、验证、刷新
   - claims.ts: 定义标准 claim 结构
   - keys.ts: RSA 密钥对管理（非对称签名）
2. 新建 src/auth/oauth/
   - authorizationServer.ts: /oauth/authorize, /oauth/token endpoints
   - clientRegistry.ts: OAuth client 管理
   - grantTypes.ts: authorization_code + client_credentials
3. Redis 配置
   - 新建 src/config/redis.ts
   - Refresh token 存储 + TTL 自动过期

### Phase 2: 中间件兼容层
4. 修改 src/auth/middleware.ts
   - 新建 hybridAuth 中间件：先检查 JWT，fallback 到旧 API Key
   - 30 天后移除 API Key fallback
5. 新建 src/auth/permissions.ts
   - 细粒度权限模型：resource:action 格式
   - 从 JWT claims 中解析权限

### Phase 3: 路由迁移
6. 逐个更新 14 个路由文件，从 requireAuth 换成 hybridAuth
7. 新增 /oauth/* 路由

### Phase 4: 测试和文档
8. 更新所有认证相关测试
9. 新增 OAuth 流程集成测试
10. 更新 API 文档，标注迁移指南

### 预计改动
- 新建文件：9 个
- 修改文件：16 个（含测试）
- 预计工时：2-3 小时（Claude 执行）

### 需要你确认
- RSA 密钥用 2048 还是 4096 bit？（建议 2048，性能更好，安全性够用）
- Access token TTL 建议 15 分钟，Refresh token TTL 7 天，可以吗？
- 要不要加 token 黑名单机制（用于主动撤销）？
```

你看完计划，觉得总体 OK，但有调整：

```text
> 几个修改：
> 1. 用 4096 bit RSA，这个项目对安全要求高
> 2. 加上 token 黑名单，用 Redis 实现
> 3. Phase 3 不要一次改 14 个路由，分两批：先改核心路由（用户认证、支付），
>    确认稳定后再改其他的

Claude: 计划已更新。主要变更：
- RSA 密钥升级为 4096 bit
- Phase 2 新增 tokenBlacklist.ts（Redis SET + TTL）
- Phase 3 拆分为 3a（6 个核心路由）和 3b（8 个非核心路由），中间加验证步骤

确认执行？
```

```text
> 确认，开始执行。
```

**第三步：执行**

切回 Normal Mode（`Shift+Tab`），Claude 按确认后的计划逐步执行。因为之前已经用 Extended Thinking 深入分析过代码，用 Planning Mode 敲定了方案，执行阶段基本不会跑偏。

这就是三个功能配合的完整流程：**Extended Thinking 提供深度分析 → Planning Mode 结构化方案 → 确认后执行**。

### 日常使用建议

不是每个任务都需要这么重的流程。实际建议：

| 任务类型 | 推荐配置 |
|---------|---------|
| 改个 bug、加个小功能 | 默认模式，不开 Extended Thinking |
| 写新模块（几个文件） | Planning Mode，`/effort medium` |
| 大规模重构、架构变更 | Planning Mode + `/effort high` 或 `max` |
| 团队标准工作流 | 打包成 Plugin |

**日常开发用默认模式就够了**，别把简单事情复杂化。碰到大任务先切 Planning Mode 理清思路，遇到难题开 Extended Thinking 深入分析，有了成熟的工作流就打包成 Plugin。循序渐进，按需使用。

## 参考链接

- [Claude Code 官方文档](https://code.claude.com/docs/en)
- [Plugins 官方参考](https://code.claude.com/docs/en/plugins-reference)
- [官方 Plugin 示例仓库](https://github.com/anthropics/claude-code/tree/main/plugins)
- [Planning Mode 工作流文档](https://code.claude.com/docs/en/common-workflows)
- [Extended Thinking 文档](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [claude-howto 学习指南](https://github.com/luongnv89/claude-howto)
