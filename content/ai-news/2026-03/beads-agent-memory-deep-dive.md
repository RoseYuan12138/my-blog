---
title: "深入理解 Beads：为什么 AI Agent 需要一个专属的记忆系统"
date: 2026-03-11
tags:
  - AI Agent
  - 开发工具
  - 内存系统
  - 图结构
  - Dolt
lang: zh
---

> 这是对 GitHub Trending 项目 [Beads](https://github.com/steveyegge/beads) 的深度分析。本篇深入讲解 Beads 背后的设计思想和工作原理。

## 零、Beads 是什么

[Beads](https://github.com/steveyegge/beads) 由 Steve Yegge 开发，是一个 **为 AI coding agent 专属设计的持久化记忆系统**。

核心概念很简单：
- **问题**：LLM coding agent（如 Claude Code、Codex）无法跨 session 保持上下文，长期开发任务时常"失忆"
- **解决方案**：用结构化的、git-backed 的图结构（DAG）作为 agent 的"大脑"，替代混乱的 markdown 计划文件
- **工作方式**：Agent 可以通过 `bd ready` 自动发现当前可以做的任务，通过 `bd claim` 认领，通过 `bd update` 更新进度

底层驱动是 [Dolt](https://github.com/dolthub/dolt)（版本控制的 SQL 数据库），支持分布式多 agent 协作、cell-level merge、完整的审计轨迹。

**18.7k+ GitHub stars**，Steve Yegge 花了 40 天 40 夜 vibe coding，先烧掉了 350k 行代码的 vibecoder 项目，从灰烬中诞生了 Beads。

---

## 一、核心问题：Agent 为什么会"失忆"

### 1.1 LLM 上下文窗口是有限的

所有基于 LLM 的 coding agent 都面临同一个硬约束：**上下文窗口有 token 上限**。

Claude 有 200k tokens，GPT-4o 有 128k tokens——看起来很多，但一个中等规模的项目，光是代码文件就能轻松占满。更关键的是，agent 在一次 session 中需要同时装下：

- 系统提示词（system prompt）
- 用户的对话历史
- 读过的代码文件
- 工具调用的输入输出
- 正在思考的推理过程

当这些加起来逼近窗口极限时，LLM 运行时会做 **compaction**（上下文压缩）——把早期的对话和文件内容压缩或丢弃，只保留摘要。这就是"失忆"的物理原因。

```
Session 1: [系统提示 | 任务背景 | 代码A | 代码B | 对话...]  → token 用完，session 结束
                                                              ↓
Session 2: [系统提示 | ???]  → agent 不知道 Session 1 做了什么
```

### 1.2 长期任务如何跨越多个 session

现实中的开发任务不是"写一个函数"这么简单。一个典型的功能开发流程是：

1. 理解需求 → 2. 设计方案 → 3. 写代码 → 4. 写测试 → 5. code review → 6. 修复 review 意见 → 7. 集成测试 → 8. 上线

这个过程可能跨越几天、几十个 session。每次 session 切换，agent 都要重新理解"我之前做了什么"。

更麻烦的是**任务嵌套**：修 UI 组件时发现数据库接口有 bug，先去修数据库，修数据库时又发现缺一个 migration 脚本——人类靠大脑里的"工作栈"来管理这种嵌套，agent 做不到。

### 1.3 Markdown 计划文件为什么会腐烂

很多人（包括 Beads 的作者 Steve Yegge）尝试过最直觉的方案：让 agent 把计划写成 markdown 文件。

这个方案有三个致命问题：

**第一，无结构化的堆积。** Agent 每次创建新计划时，倾向于新建文件而不是更新旧文件。Steve Yegge 在开发 vibecoder 时积累了 **605 个 markdown 计划文件**——他自己都找不到哪个是当前的。

**第二，信息腐烂。** 一个计划写完后，实际执行中需求会变、设计会改、依赖会断。但旧的 markdown 文件不会自动更新，结果就是磁盘上同时存在多个互相矛盾的"真相"。

**第三，没有语义关系。** 文件是扁平的——plan-001 和 plan-002 之间是什么关系？谁依赖谁？哪个已经完成了？哪个被废弃了？全靠 agent 去读文件内容来推断，而推断经常出错。

```
plans/
├── plan-001-ui-redesign.md        ← 三周前的，部分完成
├── plan-002-api-refactor.md       ← 两周前的，已废弃但没标注
├── plan-003-ui-redesign-v2.md     ← 一周前的，是 001 的修订版
├── plan-004-hotfix.md             ← 三天前的，已完成但没删
├── plan-005-testing.md            ← 昨天的，依赖 003 但没写明
└── ... (还有 600 个)
```

Agent 看到这个目录时的内心 OS：哪个是当前要做的？我不知道。

## 二、Beads 的解法：图结构 + 版本化数据库

### 2.1 从线性列表到依赖图

Beads 的核心思想是：**任务之间的关系不是线性的，而是图结构的**。

想一下你脑子里是怎么管理工作的——不是一个 TODO list，而是一张网。"要做 A 得先完成 B"，"C 和 D 可以并行"，"E 已经不需要了因为需求变了"。这就是一个**有向无环图**（DAG, Directed Acyclic Graph）。

DAG 的关键好处：

| 特性 | 线性 TODO | DAG 依赖图 |
|------|-----------|-----------|
| 执行顺序 | 固定的从上到下 | 由依赖关系决定，支持并行 |
| 阻塞检测 | 手动判断 | 自动：有前置未完成 = 阻塞 |
| 任务发现 | 人类指定下一个 | `bd ready` 自动找出所有可执行任务 |
| 嵌套任务 | 难以表达 | 天然支持（子图） |
| 废弃传播 | 手动逐个标记 | 关闭父任务，子任务级联更新 |

### 2.2 Beads 的图结构详解

Beads 中的每个任务（bead）可以有以下关系：

```
关系类型          含义                    例子
─────────────────────────────────────────────────
blocks           B 阻塞 A（A 必须等 B）    数据库 migration blocks API 开发
relates_to       相关但不阻塞              两个 UI 组件互相关联
duplicates       重复任务                  两个人提了同一个 bug
supersedes       替代旧任务                新方案替代旧方案
replies_to       回复（消息类型）           agent 间通信
parent-child     层级关系                  Epic → Task → Sub-task
```

这些关系构成了一个知识图谱。Agent 通过查询这个图就能回答：

- "现在什么任务可以做？"（`bd ready`：找所有入度为 0 且状态为 open 的节点）
- "这个任务为什么被阻塞？"（沿 blocks 边回溯）
- "这个功能的全貌是什么？"（从 Epic 节点遍历子图）

### 2.3 用伪代码理解 `bd ready`

```python
def find_ready_tasks(graph):
    """找出所有可以立即开始的任务"""
    ready = []
    for task in graph.all_tasks():
        if task.status != "open":
            continue
        if task.assignee and task.assignee != current_agent:
            continue  # 已被其他 agent 认领
        
        # 检查所有阻塞者是否已完成
        blockers = graph.get_blockers(task)
        all_resolved = all(b.status == "closed" for b in blockers)
        
        if all_resolved:
            ready.append(task)
    
    return sorted(ready, key=lambda t: t.priority)  # P0 优先
```

这就是 `bd ready` 的核心逻辑——在一个 DAG 上做拓扑排序的变体，找出所有"就绪"节点。

### 2.4 状态转移

每个 bead 有生命周期：

```
              claim
  open ──────────────► in_progress
   │                       │
   │ close                 │ close
   │                       │
   ▼                       ▼
 closed ◄─────────── closed
   │
   │ compact
   ▼
 compacted (语义摘要)
```

Agent 通过 `bd update <id> --claim` 原子性地认领任务（设置 assignee + in_progress），避免多 agent 重复认领。

## 三、为什么 Dolt 是关键

### 3.1 为什么不用 SQLite 或 PostgreSQL？

最直接的问题：为什么不用现成的数据库？

**SQLite** 的问题是单写者模型——同一时间只有一个进程能写入。当你有多个 agent 并行工作时，这是个硬伤。更重要的是，SQLite 没有版本控制能力——你没法 branch、diff、merge。

**PostgreSQL** 的问题是部署复杂度——它需要一个持续运行的 server 进程。Beads 的设计目标是"安装一个 CLI，cd 到你的项目目录，`bd init`"，不应该要求用户先装一个数据库服务器。

而 **Dolt** 完美匹配了 Beads 的需求：

| 需求 | SQLite | PostgreSQL | Dolt |
|------|--------|------------|------|
| 零运维（嵌入式） | ✅ | ❌ | ✅ |
| 版本控制 | ❌ | ❌ | ✅ |
| 分支 + 合并 | ❌ | ❌ | ✅ |
| SQL 查询 | ✅ | ✅ | ✅（MySQL 兼容） |
| 分布式同步 | ❌ | 需要额外工具 | ✅（原生 remote） |
| Cell 级别 merge | N/A | N/A | ✅ |

### 3.2 Cell-level Merge vs File-level Conflict

这是 Dolt 最核心的优势，值得展开讲。

用 Git 管理数据时，如果两个分支修改了同一个 JSON 文件的不同字段，Git 会报冲突——因为 Git 的 merge 粒度是**行（line）**。

```
# Git 的痛点
Branch A 修改了 tasks.json 第 42 行：把任务 X 的状态改为 "done"
Branch B 修改了 tasks.json 第 43 行：把任务 Y 的优先级改为 P0

Git: "CONFLICT in tasks.json" ← 但这两个修改其实完全不相关！
```

Dolt 的 merge 粒度是**单元格（cell）**——表中的每一行的每一列独立追踪。两个分支修改了同一张表的不同行（甚至同一行的不同列），可以自动无冲突合并。

```
# Dolt 的做法
Branch A: UPDATE tasks SET status='done' WHERE id='bd-a1b2';
Branch B: UPDATE tasks SET priority=0 WHERE id='bd-c3d4';

Dolt: 自动合并 ✅ （不同行，零冲突）

# 甚至：
Branch A: UPDATE tasks SET status='done' WHERE id='bd-a1b2';
Branch B: UPDATE tasks SET priority=0 WHERE id='bd-a1b2';

Dolt: 自动合并 ✅ （同一行但不同列，用三路合并）
```

在多 agent 场景下，这个特性至关重要。Agent A 在认领任务 X，Agent B 在关闭任务 Y——如果用 Git 管理，合并时几乎必然冲突；用 Dolt，无痛合并。

### 3.3 分布式同步与审计轨迹

Dolt 内建了类似 Git 的 remote 概念。`bd sync` 可以把本地的 Dolt 数据库推送到远端（DoltHub 或自建 remote），其他 agent 或其他机器拉取后就能看到完整的任务状态。

同时，Dolt 的每次写入都自动生成一个 commit——这意味着你有完整的审计轨迹（audit trail）：

```sql
-- 查看任务 bd-a1b2 的完整修改历史
SELECT * FROM dolt_history_tasks WHERE id = 'bd-a1b2' ORDER BY commit_date;

-- 结果：
-- commit_hash  | date       | author  | status       | priority
-- abc123       | 2026-03-01 | human   | open         | P1
-- def456       | 2026-03-02 | agent-1 | in_progress  | P1
-- ghi789       | 2026-03-05 | agent-1 | in_progress  | P0  ← 优先级被调高
-- jkl012       | 2026-03-08 | agent-2 | closed       | P0
```

这种 temporal data 能力意味着你可以回答"这个任务是什么时候被谁改成 P0 的"——在调试和复盘时非常有价值。

## 四、Hash ID 的智慧

### 4.1 为什么不用自增 ID？

在传统数据库中，任务 ID 通常是自增整数（1, 2, 3, ...）。这在单机单用户场景下没问题，但在 Beads 的场景下是灾难性的：

```
Agent A 在 branch-a 上创建任务，ID = 42
Agent B 在 branch-b 上创建任务，ID = 42  ← 冲突！

合并时：两个完全不同的任务有了相同的 ID
```

### 4.2 Hash 的确定性命名

Beads 用**内容 hash**（基于任务标题、创建时间等信息的哈希值前几位）来生成 ID，如 `bd-a1b2`。这意味着：

- **同一个任务**在不同分支上创建，只要输入相同，ID 就相同
- **不同的任务**，几乎不可能产生相同的 ID
- **不需要中央协调**——每个 agent 独立生成 ID，合并时不会冲突

这就是分布式系统中经典的**确定性命名**思路——UUID 的精简版。4 个十六进制字符 = 65,536 种可能。听起来不多？但配合层级结构（`bd-a3f8.1.2`），实际命名空间是足够的。而且碰撞时 Beads 会自动延长 hash 来消歧。

### 4.3 Hash 冲突概率

用生日悖论估算：在 65,536 个可能的 4 字符 hex ID 中，大约创建 **256 个任务**后，冲突概率达到 50%。

但实际工程中，一个项目很少同时有几百个活跃任务。而且 Beads 使用的是层级 ID——一个 Epic 下的子任务在各自的命名空间内，相当于每层独立计数。所以实际冲突率极低，万一遇到了，自动延长 hash 即可。

这是典型的**工程简洁性 vs 理论完美性**的权衡——hash ID 不是理论上最优的方案（UUID 更安全），但它在保证够用的前提下，极大提升了可读性和可用性。你能记住 `bd-a3f8`，但你记不住 `550e8400-e29b-41d4-a716-446655440000`。

## 五、Memory Compaction：和 Token 有限性的博弈

### 5.1 为什么要压缩旧任务

Agent 每次启动时需要通过 `bd prime` 加载当前工作状态到上下文中。如果数据库里有几百个任务、每个都有完整的描述和讨论历史，光是加载任务列表就可能消耗几万 tokens。

所以 Beads 引入了 **compaction**（压缩/衰减）机制：已关闭的旧任务，会被语义压缩成简短的摘要。

### 5.2 语义压缩的工作方式

```
压缩前（原始任务，~500 tokens）：
─────────────────────────────
Title: 修复用户登录时的 OAuth token 刷新竞态条件
Status: closed
Priority: P0
Description: 在高并发场景下，当两个请求同时尝试刷新 OAuth token 时，
            存在竞态条件。第二个请求会使用已失效的旧 token...
            (详细的技术描述、复现步骤、修复方案、测试结果、讨论记录)

压缩后（摘要，~50 tokens）：
─────────────────────────────
[bd-a1b2] OAuth token 刷新竞态条件 — 已修复。
方案：用 Redis 分布式锁保证单次刷新。影响：auth 模块。
```

信息量从 500 tokens 降到 50 tokens，**10 倍压缩**。关键信息（做了什么、怎么做的、影响范围）保留了，细节（复现步骤、讨论过程）丢弃了。

这就像人类的记忆——你记得去年修过一个 OAuth 的并发 bug，方案是用分布式锁，但你不记得具体的代码是怎么写的。需要细节的时候，你知道去哪里找（git log、PR 记录）。

### 5.3 Token 预算管理

一个实际的 token 预算分配可能是这样的：

```
Agent 的上下文窗口：200,000 tokens

分配：
├── 系统提示                    ~5,000 tokens
├── 当前对话历史                ~30,000 tokens
├── 当前正在编辑的代码文件       ~50,000 tokens
├── 工具调用的输入输出           ~30,000 tokens
├── Beads 任务状态（bd prime）   ~5,000 tokens  ← 压缩后的全局画面
└── 剩余用于推理                ~80,000 tokens
```

如果没有 compaction，任务状态可能需要 50,000+ tokens——占了四分之一的上下文。压缩到 5,000 tokens 后，agent 依然知道全局画面，但有更多空间用于实际工作。

Beads 还支持 `bd purge` 命令，可以彻底删除已关闭的临时任务（wisps），进一步回收存储空间。

## 六、与其他方案的对比

### 6.1 Git Commit Message 作为记忆

最原始的方案：通过读 git log 来了解项目历史。

问题：
- **信号噪声比极低**。一个项目可能有几千条 commit，大部分是 "fix typo"、"update deps"
- **没有结构**。Commit 是线性的，无法表达依赖、阻塞、优先级
- **没有未来视角**。Commit 只记录"做了什么"，不记录"还要做什么"
- **无法查询**。"哪些任务在等这个 PR？"——git log 回答不了

### 6.2 Notion / Linear / Jira

这些是人类用的项目管理工具。为什么不让 agent 也用？

| 问题 | 说明 |
|------|------|
| API 延迟 | 每次查询都是 HTTP 请求，几百毫秒起步。Agent 每分钟可能查询几十次 |
| Token 消耗 | API 返回的 JSON 冗长，大量无用字段消耗上下文 |
| 无离线能力 | 没网就没法工作 |
| 非 agent 优化 | 返回的数据格式为人类 UI 设计，不是为 LLM 消费设计 |
| 无版本控制 | 没有 branch/merge，多 agent 并行修改困难 |
| 权限复杂 | 需要 OAuth、API key 配置，增加 agent 的 setup 成本 |

### 6.3 AGENTS.md / CLAUDE.md

目前很多 coding agent 用的方案——在仓库根目录放一个 markdown 文件，记录指令和上下文。

这比 605 个散落的计划文件好，但本质上还是**单文件、无结构**：

- 文件会越来越长，最终超过 agent 的上下文窗口
- 没有任务状态管理——全靠 agent 自己读文本来判断
- 没有多 agent 协调能力
- 没有历史版本（除了 git diff，粒度太粗）

### 6.4 为什么必须专门为 AI Agent 设计

总结一下 Beads 做对了什么：

1. **JSON 输出**：所有 `bd` 命令都支持 `--json`，LLM 原生友好
2. **本地优先**：嵌入式数据库，零延迟查询
3. **按需加载**：`bd ready` 只返回当前需要的信息，不浪费 token
4. **原子操作**：`bd update --claim` 是原子的，多 agent 不会打架
5. **自动审计**：每次操作自动记录到 Dolt 历史，不需要 agent 额外维护
6. **渐进式采用**：`bd init` 一行命令，不需要改项目结构

## 七、应用场景

### 7.1 长周期开发任务

这是 Beads 最直接的应用场景。一个跨越多天的功能开发：

```
Day 1, Session 1: agent 创建 Epic，分解为 5 个子任务
Day 1, Session 2: agent 完成子任务 1、2
Day 2, Session 3: agent 醒来，bd ready → 看到子任务 3 可以做
Day 3, Session 4: 新的 bug 被发现，agent 创建紧急任务并设置 blocks 关系
Day 4, Session 5: bug 修复后，原来被阻塞的子任务自动变为 ready
```

每次 session 切换，agent 不需要人类重新 brief，它自己就知道该做什么。

### 7.2 多 Agent 协作

当你同时启动多个 agent（比如一个写前端、一个写后端、一个写测试）：

- 每个 agent 在独立分支上工作
- 通过 Beads 共享任务状态
- 用 `bd update --claim` 避免重复认领
- Dolt 的 cell-level merge 确保合并无冲突

### 7.3 在推荐系统中的潜力

这个场景对 Rose 应该特别有意义。

推荐系统的模型迭代是一个典型的长周期、多依赖任务：

```
bd-f1a2 (Epic: 推荐模型 V3 迭代)
├── bd-f1a2.1 (数据管线更新)
│   ├── bd-f1a2.1.1 (新增用户行为特征)
│   └── bd-f1a2.1.2 (特征工程优化)
├── bd-f1a2.2 (模型训练, blocks: bd-f1a2.1)
│   ├── bd-f1a2.2.1 (超参搜索)
│   └── bd-f1a2.2.2 (A/B 实验配置)
├── bd-f1a2.3 (线上评估, blocks: bd-f1a2.2)
└── bd-f1a2.4 (清理旧模型, blocks: bd-f1a2.3)
```

如果你用 agent 来辅助模型迭代（自动跑实验、分析指标、调超参），Beads 可以帮 agent 记住：哪些实验跑过了、什么配置效果好、下一步该做什么。特别是在 A/B 实验这种"一个实验的结论决定下一个实验的方向"的场景，依赖图的表达力比线性 TODO 强太多。

## 八、Beads 项目现状

- **GitHub Stars**: 18.7k+，势头强劲
- **作者**: Steve Yegge（前 Google / Amazon 知名工程师）
- **支持的 Agent**: Claude Code、Sourcegraph Amp、OpenAI Codex、GitHub Copilot 等
- **安装方式**: npm / Homebrew / Go / 一键脚本，多平台支持
- **社区生态**: 已有社区贡献的 [终端 UI、Web UI、编辑器扩展](https://github.com/steveyegge/beads/blob/main/docs/COMMUNITY_TOOLS.md)

## 九、我的总结

Beads 解决了一个真实的、被大多数人低估的问题：**AI agent 的记忆是断裂的**。

在"vibe coding"越来越普及的今天，越来越多的人开始让 agent 做复杂的、多步骤的开发工作。但大部分人还在用 markdown 文件或者口头 brief 来给 agent 传递上下文——这就像给一个失忆症患者贴便利贴一样，勉强能用，但效率很低。

Beads 的设计哲学是：**给 agent 一个原生的、结构化的、持久化的记忆系统**，让它自己管理工作，而不是依赖人类每次手动恢复上下文。

几个特别精妙的设计：

1. **DAG 任务图** —— 让 agent 自己发现工作，而不是等人类指派
2. **Dolt 的 cell-level merge** —— 让多 agent 并行成为可能
3. **Hash ID** —— 用工程简洁性换来分布式友好
4. **Memory compaction** —— 优雅地在信息量和 token 预算之间做平衡

如果你在做任何比 "hello world" 复杂一点的 agent 辅助开发，Beads 值得认真了解一下。

## 参考链接

- [GitHub: steveyegge/beads](https://github.com/steveyegge/beads)
- [Steve Yegge: Introducing Beads (Medium)](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a)
- [Steve Yegge: Beads Best Practices (Medium)](https://steve-yegge.medium.com/beads-best-practices-2db636b9760c)
- [Dolt: Git for Data](https://github.com/dolthub/dolt)
- [DoltHub Blog: A Day in Gas Town](https://www.dolthub.com/blog/2026-01-15-a-day-in-gas-town/)
- [Beads Agent Workflow 指南](https://github.com/steveyegge/beads/blob/main/AGENT_INSTRUCTIONS.md)
- [Beads 安装指南](https://github.com/steveyegge/beads/blob/main/docs/INSTALLING.md)
- [Beads 社区工具](https://github.com/steveyegge/beads/blob/main/docs/COMMUNITY_TOOLS.md)
- [Beads DeepWiki](https://deepwiki.com/steveyegge/beads)
