---
title: "OpenClaw-RL + Telegram in Practice: Training Your Own Chat Model with Tinker Cloud"
date: 2026-03-14
tags:
  - OpenClaw
  - Reinforcement Learning
  - Telegram
  - Tinker
lang: en
chinese: ai-agent/openclaw/openclaw-rl-telegram
---

> 🧠 **Paper theory** → [[../papers-reading/openclaw-rl.en|OpenClaw-RL: Train Any Agent Simply by Talking]] | **This post is a hands-on deployment guide**
>
> For a deep dive into the OpenClaw-RL paper theory, see the link above. This post documents the complete workflow of connecting OpenClaw-RL to Telegram — starting from zero setup to having your AI Agent continuously improve through conversation.

## Background

I wanted my OpenClaw agent Lingro (my AI companion/coach) to stop relying on the Claude API and instead run on a model I can continuously train myself. The goal is simple: chat with Lingro on Telegram, have the conversations automatically collected, and trigger RL training once enough samples accumulate — the model gets better the more we talk.

The problem is I only have a Mac mini with no NVIDIA GPU. [OpenClaw-RL](https://github.com/Gen-Verse/OpenClaw-RL) paired with [Tinker](https://tinker-docs.thinkingmachines.ai/) cloud handles this — all inference and LoRA training happens in the cloud, and locally you just run a lightweight proxy. This post documents the full setup process.

Repository: **https://github.com/Gen-Verse/OpenClaw-RL**

## What is Tinker

[Tinker](https://tinker-docs.thinkingmachines.ai/) is a distributed LLM fine-tuning API. Core value: local CPU machine + cloud GPU, with Tinker abstracting away the complexity of distributed training. You can run a lightweight proxy on your Mac mini and have it forward inference and LoRA training requests to Tinker cloud.

OpenClaw-RL leverages Tinker to implement a complete conversational RL pipeline (the Personal Agent track from the [[ai-agent/papers-reading/openclaw-rl.en|paper]]):

1. **Inference**: Telegram message → OpenClaw Gateway → local proxy → Tinker cloud (cloud model generates reply)
2. **Data collection**: Conversations are automatically collected by OpenClaw-Tinker as training samples
3. **RL training**: Once a batch is full, one step of LoRA RL update runs in the cloud

OpenClaw-RL supports three training methods: OPD (online distillation), RL (reinforcement learning), and combine (both together). The combine method works best. For details on how these methods work and their experimental comparison, see the [[ai-agent/papers-reading/openclaw-rl.en#Learning Methods|learning methods section in the paper notes]].

### Supported Models on Tinker

Tinker currently supports various Qwen series models:

| Model | Type | Scale |
|-------|------|-------|
| Qwen/Qwen3-4B-Instruct-2507 | Instruction | Compact |
| Qwen/Qwen3-8B | Hybrid | Small |
| Qwen/Qwen3-8B-Base | Base | Small |
| Qwen/Qwen3-32B | Hybrid | Medium |
| Qwen/Qwen3-30B-A3B etc. | MoE / Instruction | Medium |
| Qwen/Qwen3.5-4B, 27B, 35B-A3B, 397B etc. | Hybrid + Vision etc. | Various |

Full list: https://tinker-docs.thinkingmachines.ai/model-lineup

I chose **Qwen/Qwen3-30B-A3B** (MoE architecture, 3B active parameters), a good balance of cost and quality.

## Architecture Overview

```
[Telegram User]
    ↔ Telegram Server
    ↔ [OpenClaw Gateway] (Mac local, port 18789)
    ↔ [OpenClaw-Tinker Local Proxy] http://localhost:30000
    ↔ [Tinker Cloud] Inference + LoRA Training
```

- **OpenClaw Gateway**: Connects to Telegram, manages agents, routes messages to the appropriate model
- **OpenClaw-Tinker**: An OpenAI-compatible API proxy on Mac (port 30000) that forwards requests to Tinker cloud while collecting conversations for training. It lives in the `openclaw-tinker/` subdirectory of the [OpenClaw-RL repo](https://github.com/Gen-Verse/OpenClaw-RL)
- **Tinker Cloud**: Where the actual model inference and LoRA RL training happens — no local GPU needed

Key design: you can **assign the RL model to just Lingro** while other agents continue using Claude, completely independently.

## Prerequisites

### 1. Tinker API Key

Sign up at https://auth.thinkingmachines.ai/sign-up, then create an API Key in the [Tinker Console](https://tinker-console.thinkingmachines.ai/) (looks like `tk_xxx...`).

### 2. Telegram Bot Token

Find @BotFather on Telegram, send `/newbot`, follow the prompts, and note the Token (looks like `123456789:ABCdefGHI...`).

### 3. Local Environment

- macOS (Intel or Apple Silicon)
- Node.js >= 22: `brew install node@22`
- Python 3.10+: system Python may be 3.9, use `brew install python@3.12`

## Step 1: Clone the Project and Set Up Python

```bash
# Clone OpenClaw-RL
git clone https://github.com/Gen-Verse/OpenClaw-RL.git
cd OpenClaw-RL

# Create venv with Python 3.12 (don't use system 3.9)
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv-mac
source .venv-mac/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r openclaw-tinker/requirements-mac.txt

# Verify
python -c "import tinker; import torch; print('OK')"
```

On Intel Macs, the Python path may be `/usr/local/opt/python@3.12/bin/python3.12`.

## Step 2: Start the OpenClaw-Tinker Proxy

```bash
cd /path/to/OpenClaw-RL
source .venv-mac/bin/activate
export TINKER_API_KEY="your_Tinker_API_Key"

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

Parameters:

- `--method combine`: OPD + RL combined training, best results (also `rl` or `opd`)
- `--model-name Qwen/Qwen3-30B-A3B`: Model name on Tinker, MoE with 3B active params
- `--batch-size 8`: Conversations per training step
- `--proxy-port 30000`: Local API port that OpenClaw Gateway connects to
- `--served-model-name qwen3-3b`: Model ID exposed to OpenClaw, used in config later

You should see output like:

```
============================================================
  OpenClaw-Combine Tinker Proxy ready
  0.0.0.0:30000 -> Tinker cloud
  Method: combine
============================================================
```

**Keep this terminal open.** Visiting `localhost:30000` in a browser returns 404 — that's normal (it only responds to POST requests). `[Rollout] waiting for samples: 0/8` is also normal — you need to chat enough on Telegram to fill a batch before training triggers.

## Step 3: Configure OpenClaw

### 3.1 Install OpenClaw CLI

```bash
npm install -g openclaw@latest
```

If you've never run OpenClaw before, run `openclaw onboard` to generate the base config file `~/.openclaw/openclaw.json`.

### 3.2 Register a Custom Model Provider

Add OpenClaw-Tinker as a custom model provider in `models.providers` in `~/.openclaw/openclaw.json`. If you already have other providers (e.g., Anthropic), keep them and add this alongside:

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

Key points:

- `baseUrl` points to your local Tinker proxy
- `apiKey` is `no-auth-needed` since the local proxy doesn't require auth
- The model `id` (`qwen3-3b`) **must match `--served-model-name` from the Tinker proxy startup**, otherwise requests will 404
- `api` is `openai-completions` because the Tinker proxy exposes an OpenAI-compatible interface
- To run multiple models (e.g., 3B and 8B), add multiple entries to the `models` array

### 3.3 Point Lingro to the RL Model

You don't need to change the default model — just assign the RL model to a specific agent while others keep using Claude. Find Lingro's agent definition in `agents.list` and set `model.primary` to the RL model:

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

The format is `<provider-id>/<model-id>`, so `openclaw-rl/qwen3-3b` means the model with id `qwen3-3b` under the `openclaw-rl` provider. Other agents stay on `anthropic/claude-haiku-4-5`.

## Step 4: Restart Gateway

Restart the gateway to pick up the new config:

```bash
openclaw gateway restart
```

## Gotcha: Context Window Overflow

After switching models I hit a 500 error, with Tinker returning:

```
Prompt length plus max_tokens exceeds the model's context window:
38284 prompt tokens + 2048 max_tokens > 32768
```

The cause: Lingro had accumulated many conversation rounds while running on Claude Haiku. OpenClaw packs the **full session history + SOUL.md + HEARTBEAT.md + memory recall results** into the prompt. Haiku's 200k token context window handles this fine, but Qwen's 32k window on Tinker can't — a single 454KB session file easily overflows.

The fix is simple: send `/reset` to Lingro on Telegram to start a new session, clearing the old conversation history. With a fresh session the context is empty and won't exceed the window. Just avoid chatting too long in a single session going forward.

This is an easy pitfall when migrating from a large-context model (Claude 200k) to a smaller one (Qwen 32k) — it's not a config issue, it's that the conversation history is too long.

## Switching Models

Switching models is straightforward. For example, going from 3B to 8B:

1. Restart the Tinker proxy with different `--model-name` and `--served-model-name`:

```bash
python run.py \
  --method combine \
  --model-name Qwen/Qwen3-8B \
  --batch-size 8 \
  --proxy-port 30000 \
  --served-model-name qwen3-8b
```

2. Add an 8B model entry in the `models.providers.openclaw-rl.models` array in `openclaw.json`:

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

3. Change Lingro's `model.primary` to `openclaw-rl/qwen3-8b` and restart the gateway.

## End Result

Chatting with Lingro on Telegram, conversations flow through OpenClaw Gateway → local Tinker proxy → Tinker cloud, with Qwen3 generating responses. Every conversation is automatically collected, and once the batch size is reached, an RL training step fires. The model continuously improves through conversation — exactly what the [[ai-agent/papers-reading/openclaw-rl.en|OpenClaw-RL paper]]'s Personal Agent track aims to achieve: a model that gets better the more you talk to it.

## Quick Reference

```bash
# Terminal 1: Tinker proxy (keep open)
cd /path/to/OpenClaw-RL && source .venv-mac/bin/activate
export TINKER_API_KEY="your_Key"
cd openclaw-tinker && python run.py --method combine \
  --model-name Qwen/Qwen3-30B-A3B --batch-size 8 --proxy-port 30000 \
  --served-model-name qwen3-3b

# Terminal 2: OpenClaw Gateway (keep open)
openclaw gateway restart
```

Full pipeline: **Telegram → OpenClaw Gateway → OpenClaw-Tinker (localhost:30000) → Tinker Cloud (inference + RL training)**

Repository: https://github.com/Gen-Verse/OpenClaw-RL

## References

- [[ai-agent/papers-reading/openclaw-rl.en|OpenClaw-RL: Train Any Agent Simply by Talking]] — Paper reading notes
- [OpenClaw-RL GitHub](https://github.com/Gen-Verse/OpenClaw-RL)
- [Tinker Documentation](https://tinker-docs.thinkingmachines.ai/)
- [Tinker Model Lineup](https://tinker-docs.thinkingmachines.ai/model-lineup)
