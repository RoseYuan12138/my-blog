---
title: "我用 Mac Mini + OpenClaw 搭了一个 24 小时在线的知识管家"
date: 2026-03-01
tags:
  - AI Agent
  - OpenClaw
  - Quartz
  - 知识管理
  - Mac Mini
lang: zh
english: ai-agent/openclaw-blog-workflow.en
---

> 🌐 [Read in English](./openclaw-blog-workflow.en.md)

## 为什么要做这件事

作为打工人，我们每天都在学东西——调研一个新算法、踩了一个坑、读了一篇好论文、发现一个好用的工具。但这些知识如果只留在脑子里或者散落在各种聊天记录、备忘录里，几周后就忘得差不多了。

知识的价值在于**积累的复利**。今天记下来的一个小知识点，三个月后可能刚好帮你解决一个问题；一年前整理的笔记，可能成为你写技术方案的基础。零散的知识碎片一旦被结构化、串联起来，产生的价值远大于单个知识点本身——这就是 1+1 > 2。

但问题是：**谁有时间每天整理笔记？**

工作已经够累了，下班还要打开编辑器、想标题、调格式、git push……大部分人（包括我）的博客都是三天打鱼两天晒网，最后荒废。

所以我的思路是：**把整理和发布交给 AI agent，我只负责最有价值的部分——学习和思考。**

我买了一台 Mac Mini 4，7×24 小时开着跑 OpenClaw，让它当我的"知识管家"。我在工作中随时通过聊天软件发一条消息，它就帮我整理成结构化的笔记，审核通过后自动发布到博客。整个过程就像跟一个助理发微信一样自然。

---

## 整体架构

```
我（手机/电脑）
  │
  │  通过 Telegram/Discord 随时发消息
  │  "记一下：今天学了 xxx..."
  ▼
Mac Mini 4（7×24 在线）
  │
  ├── OpenClaw（AI agent，常驻后台）
  │     ├── 接收我的消息
  │     ├── 整理成 Markdown 文章
  │     ├── 发给我审核
  │     └── 确认后 git push
  │
  └── Quartz 博客仓库（本地 clone）
        └── content/  ← 所有知识库文章
              ├── recommender-systems/
              ├── ai-agent/
              ├── astronomy/
              └── ...
                    │
                    │  git push 触发 GitHub Actions
                    ▼
              GitHub Pages（自动构建部署）
              → 博客上线 ✅
```

简单说就是：**我发消息 → Mac Mini 上的 OpenClaw 处理 → 自动发布到博客**。

---

## 为什么用 Mac Mini

OpenClaw 需要一台 7×24 在线的机器跑。用自己的主力电脑不现实（合盖就断了），云服务器又多一层延迟和成本。Mac Mini 4 正好：

- **安静、省电**，放桌子角落完全无感
- **性能够用**，跑 OpenClaw + 本地 Git 操作绑绑有余
- **macOS 生态**，跟我的其他 Apple 设备协作方便
- 社区里很多人也是专门买 Mac Mini 跑 OpenClaw

当然 Linux 服务器、Raspberry Pi、甚至旧笔记本都能做这件事，Mac Mini 只是我个人的选择。

---

## 博客平台：Quartz

博客用的是 [Quartz v4](https://quartz.jzhao.xyz/)，一个开源的静态站点生成器。选它主要因为：

- 内容就是 Markdown 文件，放在 `content/` 文件夹下，对 AI agent 来说操作非常友好
- 天然适合知识库——支持图谱视图、反向链接、wikilinks，笔记之间可以互相关联
- 配合 GitHub Pages 完全免费部署，push 到 GitHub 就自动上线

搭建过程很简单（`git clone` → `npm i` → `npx quartz create`），这里不展开了，详见 [官方文档](https://quartz.jzhao.xyz/)。

---

## OpenClaw：核心主角

### 是什么

[OpenClaw](https://openclaw.ai/)（原名 Clawdbot / Moltbot）是由 Peter Steinberger 开发的开源 AI agent。跟 ChatGPT、Claude 这些聊天机器人最大的区别是：**它不只回答问题，它能真正干活**——读写文件、运行 shell 命令、管理日历、发邮件、控制浏览器。

它在你本地运行，通过你日常使用的聊天软件（Telegram、Discord、WhatsApp、Signal 等）作为交互界面。你像给同事发消息一样跟它沟通，它在后台执行任务。

### 为什么它适合管博客

- **常驻后台**：不是用完就关的 chatbot。跑在 Mac Mini 上 7×24 在线，有 heartbeat 机制可以定期执行任务
- **聊天即界面**：我在地铁上、吃饭时、任何碎片时间都能通过 Telegram 给它发消息。不需要打开电脑、编辑器、终端
- **持久记忆**：上下文跨对话保留，它记得我的知识库结构、写作偏好、之前的文章
- **能操作文件系统**：直接在 Mac Mini 上读写 Markdown 文件、执行 git 命令，这正是管博客需要的能力
- **可定制行为**：通过 `SOUL.md` 和 skill 文件精确控制它做什么、不做什么

### 核心概念

OpenClaw 的 workspace 里有几个关键配置文件，理解它们是"调教" agent 的基础：

| 文件 | 作用 | 类比 |
|------|------|------|
| `SOUL.md` | 定义 agent 的行为规则和价值观 | 新员工的岗位职责说明 |
| `USER.md` | 关于你的信息（偏好、习惯） | 你给助理的自我介绍 |
| `IDENTITY.md` | agent 的身份设定 | 它的名片 |
| `HEARTBEAT.md` | 定时任务清单 | 每日/每周 checklist |

workspace 目录在 macOS 上的位置：`/Users/[你的用户名]/.openclaw/workspace`

这是个隐藏文件夹（`.` 开头），在 Finder 里看不到。最简单的打开方式：

```bash
open /Users/minicat/.openclaw/workspace
```

### 安全提醒

OpenClaw 很强大，但功能越大责任越大：

- 它需要广泛的系统权限（文件读写、命令执行），配置不当有安全风险
- 社区 skill 质量参差不齐，安全研究人员发现过恶意 skill
- 建议：敏感操作设为需要人工确认、不要把密码直接暴露给 agent、了解你安装的每一个 skill 在做什么
- OpenClaw 维护者自己说过："如果你连命令行都不会用，这个项目对你来说太危险了"

---

## 怎么"调教"OpenClaw 帮我管博客

这是本文的核心。搭好 Quartz 和 OpenClaw 之后，需要解决三个问题：

1. 怎么让 bot 知道博客怎么更新
2. 怎么规范化它的写作行为
3. 写完之后怎么给我审核、按要求修改

我的思路是：**把所有规则写成文档，让 bot 自己读。** 不要试图在对话里口头交代——它会忘。写成持久化的文件，它每次都能参考。就像给新员工写 onboarding 文档，文档越清晰，它上手越快，犯错越少。

具体来说，我写了两个核心文件放到 workspace 里。

### 文件一：`BLOG_INSTRUCTIONS.md`（技术操作手册）

这个文件告诉 bot 所有技术层面的事情。

**仓库信息**：本地路径在哪、远程仓库地址、用哪个分支。

**目录结构规则**：我的知识库按领域组织，会不断扩展新主题：

```
content/
├── recommender-systems/       # 推荐系统
│   ├── index.md               # 领域概览
│   ├── algorithms/            # 子领域：算法
│   │   ├── collaborative-filtering.md        # 中文版
│   │   └── collaborative-filtering.en.md     # 英文版
│   └── architecture/          # 子领域：架构
├── ai-agent/                  # AI Agent
├── astronomy/                 # 天文学（业余爱好）
└── ...                        # 随时加新领域
```

文件夹命名用小写英文加连字符（`recommender-systems`），文章多了再拆子目录，每个文件夹有个 `index.md` 做概览。

**Frontmatter 格式**：每篇 Markdown 文章开头必须有 YAML 头信息，包括标题、日期、标签、语言标记和对应翻译版本的路径：

```yaml
---
title: "协同过滤算法详解"
date: 2026-03-01
tags:
  - 推荐系统
  - 算法
lang: zh
english: recommender-systems/algorithms/collaborative-filtering.en
---
```

**双语规则**：因为我在国外生活，想同时维护中英文版本。中文是主版本（`.md`），英文是翻译版（`.en.md`），文章顶部各放一个切换链接。Quartz 不原生支持文章级的语言切换按钮，所以先用这个简单方案跑起来。

**Git 流程和红线**：写完等我确认再 push，不动配置文件，不删已有文章，不确定的内容标 `[TODO]` 而不是瞎编。

### 文件二：`WRITING_GUIDE.md`（写作规范 + 审核流程）

这个文件告诉 bot 行为层面的事情——什么时候写、怎么写、怎么跟我互动。

**触发词系统**是关键设计。不是我说的每句话都该变成文章，所以约定了一组关键词：

| 我说 | bot 做什么 |
|---|---|
| `记一下：...` | 整理成博客笔记，发给我审核 |
| `发布：...` | 整理并准备发布 |
| `更新 [文章名]：...` | 在已有文章中追加内容 |
| `翻译 [文章名]` | 为指定文章生成英文版 |
| 没有触发词 | 当普通聊天，不自动写文章 |

**写作风格**定义为学习笔记风——简洁直接、不过度润色、保留真实思考过程。每篇文章要有核心概念、关键点、代码或示例（如果有）、参考链接。

**知识库管理职责**：bot 不只是写文章，还要主动维护知识库的健康——定期检查目录是否需要重组、更新 `index.md`、提醒我补充 `[TODO]`、发现可以互相关联的文章时添加 wikilinks。

**审核流程**是整个工作流的最后一环。我选了最轻量的聊天审核模式：

```
我发内容
  ↓
bot 整理成 Markdown 文章
  ↓
在聊天里发给我预览（附带建议的文件路径和标签）
  ↓
我说"可以" → bot 生成英文版 → 发我快速过目 → 确认 → git push → 发布 ✅
我说"改一下 xxx" → bot 修改 → 重新发完整文章 → 循环
我说"先存着" → 保存到 drafts 目录，不发布
```

所有操作都在 Telegram 里完成，不需要打开电脑。

---

## 配置步骤

### 1. 把指令文件放到 workspace

```bash
cp BLOG_INSTRUCTIONS.md /Users/minicat/.openclaw/workspace/
cp WRITING_GUIDE.md /Users/minicat/.openclaw/workspace/
```

### 2. 在 SOUL.md 里引用

在 OpenClaw 的 `SOUL.md` 里加一段，让 agent 知道它有这个职责：

```markdown
## 博客管理

你是 Rose 的个人知识库管理助手。在处理任何博客相关的任务之前，先阅读：
- BLOG_INSTRUCTIONS.md（技术操作指南）
- WRITING_GUIDE.md（写作规范和审核流程）

严格按照这两个文件的规则执行，尤其是：
- 不要自动 push，等 Rose 确认
- 不确定的内容标 [TODO]，绝不编造
- 每篇文章都要生成中英双语版本
```

### 3. 确保 Git 权限

Mac Mini 上需要能 push 到 GitHub：

```bash
cd /path/to/my-blog
git remote -v          # 确认远程仓库地址
git push --dry-run origin v4   # 测试权限
```

### 4. 测试一下

在 Telegram 里给 bot 发一条：

```
记一下：今天学了 RAG（Retrieval-Augmented Generation），
核心流程是 query → retrieve → augment prompt → generate，
可以减少 LLM 幻觉，也能回答训练数据之外的问题。
```

如果一切正常，bot 会：
1. 判断这属于哪个领域（比如 `ai-agent/`）
2. 整理成带 frontmatter 的 Markdown 文章
3. 在 Telegram 里发给你预览
4. 等你说"可以"后生成英文版、执行 git push

---

## 用了一段时间的感受

**好用的地方**：

- 真正降低了记录的门槛。以前想到什么要打开电脑才能记，现在发条消息就行，地铁上、吃饭时都能操作
- 知识库在慢慢长大，而且是结构化的。比随手记在备忘录里好找太多
- 双语版本自动生成省了很多事。虽然翻译质量偶尔要调，但 80% 的情况直接能用
- bot 主动维护知识库结构这一点超出预期，它会提醒我"你有 3 篇关于 embedding 的笔记，建议创建子目录"

**还需要改进的地方**：

- bot 偶尔会过度整理，把我的口语化表达"润色"成教科书风格——需要在 WRITING_GUIDE 里更强调"保留原始表达"
- 双语切换还只是顶部的一个链接，体验不够好。后续考虑改 Quartz 组件做真正的切换按钮
- 知识库大了之后，分类边界会模糊（比如一篇关于 "RAG 在推荐系统中的应用" 该放 `ai-agent/` 还是 `recommender-systems/`），需要更好的交叉引用机制

---

## 总结

核心公式：**Mac Mini（硬件） + OpenClaw（agent） + Quartz（博客） + 两个指令文件（规则）**。

关键 insight 是：**把规则写成文档，让 bot 自己读。** 不要口头交代，它会忘。写成 `BLOG_INSTRUCTIONS.md`（技术层：怎么操作）和 `WRITING_GUIDE.md`（行为层：怎么写、怎么审核），bot 每次执行任务前都会参考。就像给新员工写 onboarding 文档——文档越清晰，它上手越快，犯错越少。

有了这套体系，积累知识就变成了"随手发条消息"那么简单。长期坚持下来，你的知识库会成为你最有价值的个人资产。

---

## 参考

- [OpenClaw 官网](https://openclaw.ai/)
- [Quartz 官方文档](https://quartz.jzhao.xyz/)
- [Quartz GitHub](https://github.com/jackyzha0/quartz)
