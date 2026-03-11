---
title: "Understanding Beads: Why AI Agents Need a Dedicated Memory System"
date: 2026-03-11
tags:
  - AI Agent
  - Developer Tools
  - Memory System
  - Graph Structure
  - Dolt
lang: en
chinese: ./beads-agent-memory-deep-dive.md
---

> This is a deep dive into the GitHub Trending project [Beads](https://github.com/steveyegge/beads), exploring the design philosophy and principles behind this innovative memory system.

## 0. What is Beads?

[Beads](https://github.com/steveyegge/beads), developed by Steve Yegge, is a **dedicated persistent memory system designed specifically for AI coding agents**.

The core concept is straightforward:
- **The Problem**: LLM coding agents (like Claude Code, Codex) lose context across sessions, frequently "forgetting" their progress in long-term development tasks
- **The Solution**: Replace messy markdown plan files with a structured, git-backed graph structure (DAG) that serves as the agent's "brain"
- **How It Works**: Agents can automatically discover what tasks are ready to work on via `bd ready`, claim tasks with `bd claim`, and update progress with `bd update`

The underlying engine is [Dolt](https://github.com/dolthub/dolt) (version-controlled SQL database), enabling distributed multi-agent collaboration, cell-level merges, and complete audit trails.

With **18.7k+ GitHub stars**, Beads is Steve Yegge's creation after 40 days of intense vibe coding. He burned down the original vibecoder project (350k LOC) due to architectural issues, and Beads emerged from the ashes.

---

## 1. The Core Problem: Why Agents "Lose Their Memory"

### 1.1 LLM Context Windows Are Finite

Every LLM-based coding agent faces the same hard constraint: **context windows have a token limit**.

Claude has 200k tokens, GPT-4o has 128k tokens — sounds like a lot, but a medium-sized project's code files alone can easily fill that up. More critically, an agent needs to fit all of the following into a single session:

- System prompt
- Conversation history
- Code files it has read
- Tool call inputs and outputs
- Its ongoing reasoning process

When these collectively approach the window limit, the LLM runtime performs **compaction** (context compression) — compressing or discarding earlier conversations and file contents, keeping only summaries. This is the physical cause of "memory loss."

```
Session 1: [System Prompt | Task Context | Code A | Code B | Conversation...]  → tokens exhausted, session ends
                                                                                ↓
Session 2: [System Prompt | ???]  → agent has no idea what happened in Session 1
```

### 1.2 How Long-Running Tasks Span Multiple Sessions

Real-world development tasks aren't as simple as "write a function." A typical feature development workflow looks like:

1. Understand requirements → 2. Design solution → 3. Write code → 4. Write tests → 5. Code review → 6. Address review feedback → 7. Integration testing → 8. Deploy

This process can span days and dozens of sessions. Every time a session switches, the agent has to re-understand "what did I do before."

Even trickier is **task nesting**: while fixing a UI component, you discover a database API bug; while fixing the database, you realize you need a migration script — humans manage this nesting with a mental "work stack," but agents can't.

### 1.3 Why Markdown Plan Files Rot

Many people (including Beads' creator Steve Yegge) have tried the most intuitive approach: have the agent write plans as markdown files.

This approach has three fatal flaws:

**First, unstructured accumulation.** Agents tend to create new files rather than update existing ones each time they make a plan. While developing vibecoder, Steve Yegge accumulated **605 markdown plan files** — he couldn't even find which one was current.

**Second, information rot.** After a plan is written, requirements change, designs evolve, and dependencies break during actual execution. But old markdown files don't auto-update, resulting in multiple contradictory "truths" coexisting on disk.

**Third, no semantic relationships.** Files are flat — what's the relationship between plan-001 and plan-002? Who depends on whom? Which ones are completed? Which are abandoned? The agent has to read file contents to infer all this, and inference frequently gets it wrong.

```
plans/
├── plan-001-ui-redesign.md        ← three weeks old, partially complete
├── plan-002-api-refactor.md       ← two weeks old, abandoned but not marked
├── plan-003-ui-redesign-v2.md     ← one week old, a revision of 001
├── plan-004-hotfix.md             ← three days old, done but not deleted
├── plan-005-testing.md            ← yesterday, depends on 003 but doesn't say so
└── ... (600 more)
```

The agent's inner monologue when seeing this directory: which one should I work on? No clue.

## 2. Beads' Solution: Graph Structure + Versioned Database

### 2.1 From Linear Lists to Dependency Graphs

Beads' core insight is: **relationships between tasks aren't linear — they form a graph structure**.

Think about how you manage work in your head — it's not a TODO list, it's a web. "To do A, I need to finish B first," "C and D can be done in parallel," "E is no longer needed because requirements changed." This is a **Directed Acyclic Graph** (DAG).

Key benefits of a DAG:

| Property | Linear TODO | DAG Dependency Graph |
|----------|-------------|---------------------|
| Execution order | Fixed top-to-bottom | Determined by dependencies, supports parallelism |
| Blocking detection | Manual judgment | Automatic: unfinished prerequisite = blocked |
| Task discovery | Human specifies the next one | `bd ready` automatically finds all executable tasks |
| Nested tasks | Hard to express | Natively supported (subgraphs) |
| Abandonment propagation | Manual one-by-one marking | Close parent task, children cascade-update |

### 2.2 Beads' Graph Structure in Detail

Each task (bead) in Beads can have the following relationships:

```
Relationship Type    Meaning                          Example
─────────────────────────────────────────────────────────────────
blocks               B blocks A (A must wait for B)   DB migration blocks API development
relates_to           Related but non-blocking          Two UI components are related
duplicates           Duplicate tasks                   Two people filed the same bug
supersedes           Replaces an older task            New approach replaces old one
replies_to           Reply (message type)              Inter-agent communication
parent-child         Hierarchical relationship         Epic → Task → Sub-task
```

These relationships form a knowledge graph. By querying this graph, an agent can answer:

- "What tasks can I work on now?" (`bd ready`: find all nodes with in-degree 0 and status open)
- "Why is this task blocked?" (trace back along `blocks` edges)
- "What's the full picture of this feature?" (traverse the subgraph from the Epic node)

### 2.3 Understanding `bd ready` with Pseudocode

```python
def find_ready_tasks(graph):
    """Find all tasks that can be started immediately"""
    ready = []
    for task in graph.all_tasks():
        if task.status != "open":
            continue
        if task.assignee and task.assignee != current_agent:
            continue  # Already claimed by another agent
        
        # Check if all blockers are resolved
        blockers = graph.get_blockers(task)
        all_resolved = all(b.status == "closed" for b in blockers)
        
        if all_resolved:
            ready.append(task)
    
    return sorted(ready, key=lambda t: t.priority)  # P0 first
```

This is the core logic of `bd ready` — a variant of topological sort on a DAG, finding all "ready" nodes.

### 2.4 State Transitions

Each bead has a lifecycle:

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
 compacted (semantic summary)
```

An agent atomically claims a task via `bd update <id> --claim` (setting assignee + in_progress), preventing multiple agents from claiming the same task.

## 3. Why Dolt Is the Key

### 3.1 Why Not SQLite or PostgreSQL?

The most direct question: why not use an existing database?

**SQLite**'s problem is its single-writer model — only one process can write at a time. When you have multiple agents working in parallel, this is a dealbreaker. More importantly, SQLite has no version control capability — you can't branch, diff, or merge.

**PostgreSQL**'s problem is deployment complexity — it requires a continuously running server process. Beads' design goal is "install a CLI, cd to your project directory, `bd init`" — it shouldn't require users to first set up a database server.

**Dolt** perfectly matches Beads' requirements:

| Requirement | SQLite | PostgreSQL | Dolt |
|-------------|--------|------------|------|
| Zero-ops (embedded) | ✅ | ❌ | ✅ |
| Version control | ❌ | ❌ | ✅ |
| Branch + merge | ❌ | ❌ | ✅ |
| SQL queries | ✅ | ✅ | ✅ (MySQL compatible) |
| Distributed sync | ❌ | Requires extra tooling | ✅ (native remote) |
| Cell-level merge | N/A | N/A | ✅ |

### 3.2 Cell-level Merge vs File-level Conflict

This is Dolt's most critical advantage, and it's worth explaining in detail.

When managing data with Git, if two branches modify different fields of the same JSON file, Git reports a conflict — because Git's merge granularity is **line-level**.

```
# Git's pain point
Branch A modified line 42 of tasks.json: changed task X's status to "done"
Branch B modified line 43 of tasks.json: changed task Y's priority to P0

Git: "CONFLICT in tasks.json" ← But these two changes are completely unrelated!
```

Dolt's merge granularity is **cell-level** — each column of each row in a table is tracked independently. Two branches modifying different rows of the same table (or even different columns of the same row) can be automatically merged without conflicts.

```
# Dolt's approach
Branch A: UPDATE tasks SET status='done' WHERE id='bd-a1b2';
Branch B: UPDATE tasks SET priority=0 WHERE id='bd-c3d4';

Dolt: Auto-merge ✅ (different rows, zero conflicts)

# Even:
Branch A: UPDATE tasks SET status='done' WHERE id='bd-a1b2';
Branch B: UPDATE tasks SET priority=0 WHERE id='bd-a1b2';

Dolt: Auto-merge ✅ (same row but different columns, using three-way merge)
```

In multi-agent scenarios, this feature is crucial. Agent A is claiming task X while Agent B is closing task Y — with Git, merging would almost certainly conflict; with Dolt, it's painless.

### 3.3 Distributed Sync and Audit Trails

Dolt has a built-in remote concept similar to Git. `bd sync` can push the local Dolt database to a remote (DoltHub or self-hosted remote), and other agents or machines can pull it to see the complete task state.

Additionally, every write in Dolt automatically generates a commit — meaning you have a complete audit trail:

```sql
-- View the complete modification history of task bd-a1b2
SELECT * FROM dolt_history_tasks WHERE id = 'bd-a1b2' ORDER BY commit_date;

-- Result:
-- commit_hash  | date       | author  | status       | priority
-- abc123       | 2026-03-01 | human   | open         | P1
-- def456       | 2026-03-02 | agent-1 | in_progress  | P1
-- ghi789       | 2026-03-05 | agent-1 | in_progress  | P0  ← priority escalated
-- jkl012       | 2026-03-08 | agent-2 | closed       | P0
```

This temporal data capability means you can answer "when and by whom was this task changed to P0" — invaluable for debugging and retrospectives.

## 4. The Wisdom of Hash IDs

### 4.1 Why Not Auto-increment IDs?

In traditional databases, task IDs are typically auto-incrementing integers (1, 2, 3, ...). This works fine in single-machine, single-user scenarios, but in Beads' context it's disastrous:

```
Agent A creates a task on branch-a, ID = 42
Agent B creates a task on branch-b, ID = 42  ← Conflict!

On merge: two completely different tasks share the same ID
```

### 4.2 Deterministic Naming with Hashes

Beads uses **content hashing** (the first few characters of a hash based on the task title, creation time, etc.) to generate IDs like `bd-a1b2`. This means:

- **The same task** created on different branches will have the same ID, as long as the inputs are identical
- **Different tasks** are virtually impossible to produce the same ID
- **No central coordination needed** — each agent generates IDs independently, with no conflicts on merge

This is the classic **deterministic naming** approach in distributed systems — a compact version of UUIDs. 4 hexadecimal characters = 65,536 possibilities. Sounds limited? But combined with hierarchical structure (`bd-a3f8.1.2`), the actual namespace is more than sufficient. And when collisions do occur, Beads automatically extends the hash to disambiguate.

### 4.3 Hash Collision Probability

Using the birthday paradox for estimation: among 65,536 possible 4-character hex IDs, the collision probability reaches 50% after creating approximately **256 tasks**.

But in practice, a project rarely has hundreds of active tasks simultaneously. Moreover, Beads uses hierarchical IDs — subtasks under an Epic have their own namespace, effectively counting independently per level. So the actual collision rate is extremely low, and if it does happen, auto-extending the hash resolves it.

This is a classic **engineering simplicity vs. theoretical perfection** tradeoff — hash IDs aren't theoretically optimal (UUIDs are safer), but they dramatically improve readability and usability while being sufficient. You can remember `bd-a3f8`, but you can't remember `550e8400-e29b-41d4-a716-446655440000`.

## 5. Memory Compaction: Wrestling with Token Limits

### 5.1 Why Compress Old Tasks

Every time an agent starts up, it needs to load the current work state into context via `bd prime`. If the database contains hundreds of tasks, each with full descriptions and discussion histories, just loading the task list could consume tens of thousands of tokens.

So Beads introduces a **compaction** (compression/decay) mechanism: old closed tasks are semantically compressed into brief summaries.

### 5.2 How Semantic Compression Works

```
Before compaction (original task, ~500 tokens):
─────────────────────────────
Title: Fix OAuth token refresh race condition during user login
Status: closed
Priority: P0
Description: Under high concurrency, when two requests simultaneously
            attempt to refresh an OAuth token, a race condition exists.
            The second request uses the already-invalidated old token...
            (detailed technical description, reproduction steps, fix plan, test results, discussion history)

After compaction (summary, ~50 tokens):
─────────────────────────────
[bd-a1b2] OAuth token refresh race condition — fixed.
Approach: Redis distributed lock for single-refresh guarantee. Impact: auth module.
```

Information reduced from 500 tokens to 50 tokens — **10x compression**. Key information (what was done, how, scope of impact) is preserved; details (reproduction steps, discussion process) are discarded.

This is like human memory — you remember fixing an OAuth concurrency bug last year using a distributed lock, but you don't remember the exact code. When you need details, you know where to find them (git log, PR records).

### 5.3 Token Budget Management

A practical token budget allocation might look like this:

```
Agent's context window: 200,000 tokens

Allocation:
├── System prompt                    ~5,000 tokens
├── Current conversation history     ~30,000 tokens
├── Code files currently editing     ~50,000 tokens
├── Tool call inputs/outputs         ~30,000 tokens
├── Beads task state (bd prime)      ~5,000 tokens  ← compressed global picture
└── Remaining for reasoning          ~80,000 tokens
```

Without compaction, task state might require 50,000+ tokens — a quarter of the context. Compressed to 5,000 tokens, the agent still knows the global picture but has much more room for actual work.

Beads also supports the `bd purge` command, which can permanently delete closed temporary tasks (wisps), further reclaiming storage space.

## 6. Comparison with Other Approaches

### 6.1 Git Commit Messages as Memory

The most primitive approach: understanding project history by reading git log.

Problems:
- **Extremely low signal-to-noise ratio.** A project might have thousands of commits, most of which are "fix typo," "update deps"
- **No structure.** Commits are linear and can't express dependencies, blocking, or priorities
- **No forward-looking perspective.** Commits only record "what was done," not "what needs to be done"
- **Not queryable.** "Which tasks are waiting on this PR?" — git log can't answer that

### 6.2 Notion / Linear / Jira

These are project management tools designed for humans. Why not let agents use them too?

| Issue | Explanation |
|-------|-------------|
| API latency | Every query is an HTTP request, starting at hundreds of milliseconds. An agent might query dozens of times per minute |
| Token consumption | API responses return verbose JSON with many useless fields that consume context |
| No offline capability | Can't work without internet |
| Not agent-optimized | Data formats are designed for human UIs, not for LLM consumption |
| No version control | No branch/merge, making parallel multi-agent modifications difficult |
| Complex permissions | Requires OAuth, API key configuration, increasing agent setup cost |

### 6.3 AGENTS.md / CLAUDE.md

The approach currently used by many coding agents — placing a markdown file in the repository root to record instructions and context.

This is better than 605 scattered plan files, but it's fundamentally still **single-file, unstructured**:

- The file keeps growing, eventually exceeding the agent's context window
- No task state management — the agent must read raw text to make judgments
- No multi-agent coordination capability
- No version history (beyond git diff, which is too coarse-grained)

### 6.4 Why a Purpose-Built Design for AI Agents Is Necessary

To summarize what Beads gets right:

1. **JSON output**: All `bd` commands support `--json`, natively LLM-friendly
2. **Local-first**: Embedded database, zero-latency queries
3. **On-demand loading**: `bd ready` returns only currently needed information, no token waste
4. **Atomic operations**: `bd update --claim` is atomic, preventing multi-agent conflicts
5. **Automatic auditing**: Every operation is automatically recorded in Dolt history, no extra maintenance by the agent
6. **Progressive adoption**: `bd init` — one command, no project structure changes needed

## 7. Use Cases

### 7.1 Long-Running Development Tasks

This is Beads' most straightforward use case. A feature development spanning multiple days:

```
Day 1, Session 1: agent creates Epic, breaks it into 5 subtasks
Day 1, Session 2: agent completes subtasks 1 and 2
Day 2, Session 3: agent wakes up, bd ready → sees subtask 3 is available
Day 3, Session 4: new bug discovered, agent creates urgent task and sets blocks relationship
Day 4, Session 5: after bug fix, previously blocked subtasks automatically become ready
```

At every session switch, the agent doesn't need a human to re-brief it — it knows what to do on its own.

### 7.2 Multi-Agent Collaboration

When you launch multiple agents simultaneously (e.g., one for frontend, one for backend, one for testing):

- Each agent works on an independent branch
- They share task state through Beads
- `bd update --claim` prevents duplicate claiming
- Dolt's cell-level merge ensures conflict-free merging

### 7.3 Potential in Recommendation Systems

This scenario should be particularly relevant to Rose.

Model iteration in recommendation systems is a classic long-running, multi-dependency task:

```
bd-f1a2 (Epic: Recommendation Model V3 Iteration)
├── bd-f1a2.1 (Data pipeline update)
│   ├── bd-f1a2.1.1 (Add user behavior features)
│   └── bd-f1a2.1.2 (Feature engineering optimization)
├── bd-f1a2.2 (Model training, blocks: bd-f1a2.1)
│   ├── bd-f1a2.2.1 (Hyperparameter search)
│   └── bd-f1a2.2.2 (A/B experiment configuration)
├── bd-f1a2.3 (Online evaluation, blocks: bd-f1a2.2)
└── bd-f1a2.4 (Clean up old models, blocks: bd-f1a2.3)
```

If you use agents to assist with model iteration (automatically running experiments, analyzing metrics, tuning hyperparameters), Beads can help the agent remember: which experiments have been run, what configurations worked well, and what to do next. Especially in A/B testing scenarios where "one experiment's conclusion determines the next experiment's direction," the expressiveness of a dependency graph far exceeds that of a linear TODO list.

## 8. Current State of the Beads Project

- **GitHub Stars**: 18.7k+, strong momentum
- **Author**: Steve Yegge (renowned engineer, formerly at Google / Amazon)
- **Supported Agents**: Claude Code, Sourcegraph Amp, OpenAI Codex, GitHub Copilot, and more
- **Installation**: npm / Homebrew / Go / one-liner script, multi-platform support
- **Community Ecosystem**: Community-contributed [terminal UI, web UI, editor extensions](https://github.com/steveyegge/beads/blob/main/docs/COMMUNITY_TOOLS.md)

## 9. My Takeaways

Beads solves a real problem that most people underestimate: **AI agent memory is fragmented**.

As "vibe coding" becomes increasingly mainstream, more and more people are letting agents handle complex, multi-step development work. But most are still using markdown files or verbal briefings to pass context to agents — this is like sticking Post-it notes on an amnesiac patient: it sort of works, but it's terribly inefficient.

Beads' design philosophy is: **give agents a native, structured, persistent memory system**, letting them manage their own work rather than relying on humans to manually restore context every time.

A few particularly elegant design choices:

1. **DAG task graph** — lets agents discover work themselves, rather than waiting for human assignment
2. **Dolt's cell-level merge** — makes multi-agent parallelism possible
3. **Hash IDs** — trades engineering simplicity for distributed friendliness
4. **Memory compaction** — elegantly balances information density against token budgets

If you're doing any agent-assisted development more complex than "hello world," Beads is worth a serious look.

## References

- [GitHub: steveyegge/beads](https://github.com/steveyegge/beads)
- [Steve Yegge: Introducing Beads (Medium)](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a)
- [Steve Yegge: Beads Best Practices (Medium)](https://steve-yegge.medium.com/beads-best-practices-2db636b9760c)
- [Dolt: Git for Data](https://github.com/dolthub/dolt)
- [DoltHub Blog: A Day in Gas Town](https://www.dolthub.com/blog/2026-01-15-a-day-in-gas-town/)
- [Beads Agent Workflow Guide](https://github.com/steveyegge/beads/blob/main/AGENT_INSTRUCTIONS.md)
- [Beads Installation Guide](https://github.com/steveyegge/beads/blob/main/docs/INSTALLING.md)
- [Beads Community Tools](https://github.com/steveyegge/beads/blob/main/docs/COMMUNITY_TOOLS.md)
- [Beads DeepWiki](https://deepwiki.com/steveyegge/beads)
