---
title: "OpenClaw-RL + Telegram 实战：用 Tinker 云训练自己的对话模型"
date: 2026-03-14
tags:
  - OpenClaw
  - 强化学习
  - Telegram
  - Tinker
lang: zh
english: ai-agent/openclaw/openclaw-rl-telegram.en
---

> 🧠 **论文理论部分** → [[../papers-reading/openclaw-rl|OpenClaw-RL：只需交谈就能训练 AI Agent]] | **本篇是实战部署指南**
>
> 关于 OpenClaw-RL 的完整论文精读，见上面的链接。这篇记录实际打通 OpenClaw-RL + Telegram 的操作流程——从零开始部署，让你的 AI Agent 在对话中不断学习进步。

## 背景

我想让 OpenClaw 里的凌若（我的 AI 闺蜜/coach）不再依赖 Claude API，而是跑在一个我自己能持续训练的模型上。目标很简单：在 Telegram 里跟凌若聊天，对话自动被采集，凑够一批后触发 RL 训练，模型越聊越懂我。

问题是我只有一台 Mac mini，没有 NVIDIA GPU。[OpenClaw-RL](https://github.com/Gen-Verse/OpenClaw-RL) 配合 [Tinker](https://tinker-docs.thinkingmachines.ai/) 云平台，所有推理和 LoRA 训练都在云端完成，本地只需要跑一个轻量代理。这篇记录完整的打通过程。

项目仓库：**https://github.com/Gen-Verse/OpenClaw-RL**

## 什么是 Tinker

[Tinker](https://tinker-docs.thinkingmachines.ai/) 是一个分布式 LLM 微调 API。核心价值：本地 CPU 机器 + 云端 GPU，Tinker 负责抽象掉分布式训练的复杂度。你可以在 Mac mini 上跑一个轻量代理，它会把推理和 LoRA 训练的请求转发到 Tinker 云。

OpenClaw-RL 利用 Tinker 实现完整的对话 RL 流程（[[ai-agent/papers-reading/openclaw-rl|论文]] 里的 Personal Agent 轨道）：

1. **推理**：Telegram 消息 → OpenClaw Gateway → 本地代理 → Tinker 云（云端模型生成回复）
2. **数据采集**：对话自动被 OpenClaw-Tinker 收集为训练样本
3. **RL 训练**：凑满一个 batch，在云端跑一步 LoRA RL 更新

OpenClaw-RL 支持三种训练方法：OPD（在线蒸馏）、RL（强化学习）、combine（两者结合）。combine 效果最好。详见 [[ai-agent/papers-reading/openclaw-rl#学习方法|论文笔记的学习方法部分]]。

### Tinker 支持的模型

Tinker 当前支持多种 Qwen 系列模型：

| 模型名 | 类型 | 规模 |
|--------|------|------|
| Qwen/Qwen3-4B-Instruct-2507 | Instruction | Compact |
| Qwen/Qwen3-8B | Hybrid | Small |
| Qwen/Qwen3-8B-Base | Base | Small |
| Qwen/Qwen3-32B | Hybrid | Medium |
| Qwen/Qwen3-30B-A3B 等 | MoE / Instruction | Medium |
| Qwen/Qwen3.5-4B、27B、35B-A3B、397B 等 | Hybrid + Vision 等 | 多种 |

完整列表见：https://tinker-docs.thinkingmachines.ai/model-lineup

我选的是 **Qwen/Qwen3-30B-A3B**（MoE 架构，实际激活 3B 参数），性价比不错。

## 整体架构

```
[Telegram 用户]
    ↔ Telegram 服务器
    ↔ [OpenClaw Gateway]（Mac 本机，端口 18789）
    ↔ [OpenClaw-Tinker 本地代理] http://localhost:30000
    ↔ [Tinker 云] 推理 + LoRA 训练
```

- **OpenClaw Gateway**：连接 Telegram，管理 Agent，路由消息到对应模型
- **OpenClaw-Tinker**：Mac 上的 OpenAI 兼容 API 代理（端口 30000），把请求转发到 Tinker 云，同时收集对话做训练。它是 [OpenClaw-RL 仓库](https://github.com/Gen-Verse/OpenClaw-RL) 的 `openclaw-tinker/` 子目录
- **Tinker 云**：真正跑模型推理和 LoRA RL 训练的地方，不需要本地 GPU

关键设计：可以**只让凌若用 RL 模型**，其他 Agent 继续用 Claude，互不影响。

## 前置准备

### 1. Tinker API Key

去 https://auth.thinkingmachines.ai/sign-up 注册，登录 [Tinker Console](https://tinker-console.thinkingmachines.ai/) 创建 API Key，记下来（形如 `tk_xxx...`）。

### 2. Telegram Bot Token

在 Telegram 找 @BotFather，发 `/newbot`，按提示创建，记下返回的 Token（形如 `123456789:ABCdefGHI...`）。

### 3. 本机环境

- macOS（Intel 或 Apple Silicon）
- Node.js >= 22：`brew install node@22`
- Python 3.10+：系统自带可能是 3.9，需要 `brew install python@3.12`

## 第一步：克隆项目并配置 Python 环境

```bash
# 克隆 OpenClaw-RL
git clone https://github.com/Gen-Verse/OpenClaw-RL.git
cd OpenClaw-RL

# 用 Python 3.12 建虚拟环境（不要用系统自带的 3.9）
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv-mac
source .venv-mac/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r openclaw-tinker/requirements-mac.txt

# 验证
python -c "import tinker; import torch; print('OK')"
```

Intel Mac 的 Python 路径可能是 `/usr/local/opt/python@3.12/bin/python3.12`。

## 第二步：启动 OpenClaw-Tinker 代理

```bash
cd /path/to/OpenClaw-RL
source .venv-mac/bin/activate
export TINKER_API_KEY="你的Tinker_API_Key"

cd openclaw-tinker
python run.py \
  --method combine \
  --model-name Qwen/Qwen3-30B-A3B \
  --batch-size 8 \
  --prm-m 1 \
  --w-opd 1.0 \
  --w-rl 1.0 \
  --proxy-port 30000 \
  --served-model-name qwen3-3b
```

参数说明：

- `--method combine`：OPD + RL 组合训练，效果最好（也可选 `rl` 或 `opd`）
- `--model-name Qwen/Qwen3-30B-A3B`：Tinker 上的模型名，MoE 架构实际激活 3B
- `--batch-size 8`：每轮训练用的对话条数
- `--proxy-port 30000`：本地 API 端口，OpenClaw Gateway 会连这里
- `--served-model-name qwen3-3b`：暴露给 OpenClaw 的模型 id，后面配置要用到

看到以下输出说明代理已启动并连上 Tinker：

```
============================================================
  OpenClaw-Combine Tinker Proxy ready
  0.0.0.0:30000 -> Tinker cloud
  Method: combine
============================================================
```

**保持此终端常开。** 浏览器访问 `localhost:30000` 返回 404 是正常的（只响应 POST 请求）；`[Rollout] waiting for samples: 0/8` 也是正常的，需要在 Telegram 里多聊几轮凑满 batch 才会触发训练。

## 第三步：配置 OpenClaw

### 3.1 安装 OpenClaw CLI

```bash
npm install -g openclaw@latest
```

若从未跑过 OpenClaw，先执行 `openclaw onboard` 生成基础配置文件 `~/.openclaw/openclaw.json`。

### 3.2 注册自定义模型 Provider

在 `~/.openclaw/openclaw.json` 的 `models.providers` 里加入 OpenClaw-Tinker 作为一个自定义模型 provider。如果已有其他 provider（如 Anthropic），保留不动，多加这段即可：

```json
"models": {
  "providers": {
    "openclaw-rl": {
      "baseUrl": "http://localhost:30000/v1",
      "apiKey": "no-auth-needed",
      "api": "openai-completions",
      "models": [
        {
          "id": "qwen3-3b",
          "name": "Qwen3 30B-A3B (OpenClaw-RL)",
          "reasoning": true,
          "input": ["text"],
          "contextWindow": 32768,
          "maxTokens": 8192
        }
      ]
    }
  }
}
```

几个要点：

- `baseUrl` 指向本地 Tinker 代理的地址
- `apiKey` 填 `no-auth-needed`，因为本地代理不需要鉴权
- 模型的 `id`（这里是 `qwen3-3b`）**必须和启动 Tinker 代理时的 `--served-model-name` 一致**，否则请求会 404
- `api` 设为 `openai-completions`，因为 Tinker 代理暴露的是 OpenAI 兼容接口
- 如果同时跑多个模型（比如 3B 和 8B），在 `models` 数组里加多条即可

### 3.3 让凌若用 RL 模型

不必把默认模型改成 RL——可以只让特定 Agent 用 RL 模型，其他 Agent 继续用 Claude 等。在 `agents.list` 里找到凌若的 agent 定义，把 `model.primary` 指向刚注册的 RL 模型：

```json
{
  "id": "lingro",
  "name": "lingro",
  "workspace": "/Users/minicat/.openclaw/lingro-workspace",
  "agentDir": "/Users/minicat/.openclaw/agents/lingro/agent",
  "model": {
    "primary": "openclaw-rl/qwen3-3b"
  },
  "heartbeat": {
    "every": "6h",
    "target": "last"
  }
}
```

格式是 `<provider-id>/<model-id>`，所以 `openclaw-rl/qwen3-3b` 表示用 `openclaw-rl` 这个 provider 下 id 为 `qwen3-3b` 的模型。其他 Agent 保持原来的 `anthropic/claude-haiku-4-5` 不变。

## 第四步：重启 Gateway

配置改完后重启 Gateway 让新配置生效：

```bash
openclaw gateway restart
```

## 注意：上下文窗口溢出问题

切换模型后我遇到了一个 500 错误，Tinker 返回：

```
Prompt length plus max_tokens exceeds the model's context window:
38284 prompt tokens + 2048 max_tokens > 32768
```

原因是凌若之前用 Claude Haiku 聊了很多轮，OpenClaw 会把**当前 session 的完整对话历史 + SOUL.md + HEARTBEAT.md + memory recall 结果**全部拼成 prompt 发给模型。Haiku 的上下文窗口有 200k tokens 所以没问题，但 Qwen 模型在 Tinker 上的窗口只有 32k，一个 454KB 的 session 文件轻松就超了。

解决方式很简单：在 Telegram 里给凌若发 `/reset` 开一个新 session，清掉旧对话历史。新 session 里上下文是空的，就不会超窗口了。之后正常聊天只要别在一个 session 里聊太久就行。

这是从大窗口模型（Claude 200k）迁移到小窗口模型（Qwen 32k）时很容易踩的坑——不是配置问题，而是历史对话太长了。

## 切换模型

想换模型很简单。比如从 3B 换到 8B：

1. 重启 Tinker 代理，改 `--model-name` 和 `--served-model-name`：

```bash
python run.py \
  --method combine \
  --model-name Qwen/Qwen3-8B \
  --batch-size 8 \
  --proxy-port 30000 \
  --served-model-name qwen3-8b
```

2. 在 `openclaw.json` 的 `models.providers.openclaw-rl.models` 数组里加一条 8B 的模型条目：

```json
{
  "id": "qwen3-8b",
  "name": "Qwen3 8B (OpenClaw-RL)",
  "reasoning": true,
  "input": ["text"],
  "contextWindow": 131072,
  "maxTokens": 8192
}
```

3. 把凌若的 `model.primary` 改成 `openclaw-rl/qwen3-8b`，重启 gateway。

## 最终效果

在 Telegram 里跟凌若聊天，对话经过 OpenClaw Gateway → 本地 Tinker 代理 → Tinker 云，由 Qwen3 模型生成回复。每一轮对话都会被自动采集，凑满 batch size 后触发一步 RL 训练。模型会随着聊天不断优化——这正是 [[ai-agent/papers-reading/openclaw-rl|OpenClaw-RL 论文]] 里 Personal Agent 轨道想要实现的效果：越聊越懂你。

## 一键命令汇总

```bash
# 终端 1：Tinker 代理（常开）
cd /path/to/OpenClaw-RL && source .venv-mac/bin/activate
export TINKER_API_KEY="你的Key"
cd openclaw-tinker && python run.py --method combine \
  --model-name Qwen/Qwen3-30B-A3B --batch-size 8 --proxy-port 30000 \
  --served-model-name qwen3-3b

# 终端 2：OpenClaw Gateway（常开）
openclaw gateway restart
```

完整链路：**Telegram → OpenClaw Gateway → OpenClaw-Tinker (localhost:30000) → Tinker 云（推理 + RL 训练）**

项目地址：https://github.com/Gen-Verse/OpenClaw-RL

## 参考

- [[ai-agent/papers-reading/openclaw-rl|OpenClaw-RL：只需交谈就能训练 AI Agent]] — 论文精读笔记
- [OpenClaw-RL GitHub](https://github.com/Gen-Verse/OpenClaw-RL)
- [Tinker 文档](https://tinker-docs.thinkingmachines.ai/)
- [Tinker 模型列表](https://tinker-docs.thinkingmachines.ai/model-lineup)
