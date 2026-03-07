---
title: "Teaching the Blog Cat a New Skill: Paper Reading"
date: 2026-03-06
tags:
  - AI Agent
  - OpenClaw
  - automation
  - paper-reading
lang: en
chinese: ai-agent/openclaw-paper-reading-skill
---

> 🌐 [中文版](./openclaw-paper-reading-skill.md)

With the [[openclaw-blog-workflow|24-hour knowledge butler]] already set up, minicat can draft notes, translate, and commit to git. But reading papers was still entirely manual — fetch the paper, extract figures, write bilingual notes, update the index, commit — a fixed process with many steps. So I decided to codify this workflow into a reusable skill.

## Motivation

The paper-to-blog workflow is highly formulaic:

```
Receive paper link
  ↓ Fetch full text (arxiv HTML > PDF)
  ↓ Extract key figures
  ↓ Write Chinese reading notes (equations, data, reflections)
  ↓ Translate to English
  ↓ Update index.md
  ↓ git commit
```

Every step has fixed logic; only the paper content varies. This is exactly the kind of thing that should be packaged as a skill.

## Design Decisions

### Figure Extraction: arxiv HTML Over PDF

Initially I tried extracting images from PDFs using PyMuPDF. A major problem surfaced: PDFs store **raw embedded images**, not the rendered composite figures. For example, a grid figure containing 4 streamer photos gets extracted as 4 separate face images, not the complete annotated figure.

Then I discovered that arxiv's HTML versions (`arxiv.org/html/ID`) contain fully rendered figures named `x1.png`, `x2.png`, etc. — exactly what you see in the paper.

The final strategy: **arxiv HTML first, PDF as fallback**. A Python script wraps both modes:

```bash
# Preferred: download complete rendered figures from arxiv HTML
python .skills/paper-reading/scripts/extract_figures.py \
  --arxiv 2602.09401 --output /tmp/figures/

# Fallback: extract embedded images from PDF
python .skills/paper-reading/scripts/extract_figures.py \
  --pdf paper.pdf --output /tmp/figures/
```

The script outputs a `manifest.json` recording each figure's filename, source URL, and size for easy selection.

### Automatic Directory Assignment

Paper reading notes go under `<domain>/papers-reading/`, auto-assigned by topic:

| Paper Domain | Directory |
|---|---|
| Recommender systems, ranking, CTR | `recommender-systems/papers-reading/` |
| Transformers, LLM architecture | `machine-learning/papers-reading/` |
| AI Agents, multi-agent systems | `ai-agent/papers-reading/` |

This naturally separates paper notes from hand-written learning notes (in `models/`, `training/`, etc.), keeping the structure clean.

### Deep-Reading Template

The default style is a **deep reading** — readers should learn the core content without needing the original paper. The article structure is fixed: core idea → system architecture (with equations) → training objectives → experimental results (with complete data tables) → reflections → references.

The "reflections" section is the most important part, requiring genuine analysis rather than paraphrasing the abstract — pointing out limitations the authors don't discuss, connections to other work, potential improvements.

A lightweight mode is also supported — saying "quick summary" produces a 1-page overview instead.

## Integrating with minicat

First, a quick note on how OpenClaw's skill system actually works. OpenClaw has a built-in skill mechanism: it scans its own global skills directory (`/opt/homebrew/lib/node_modules/openclaw/skills/`), injects each skill's `name` and `description` into the agent's system prompt, and loads the full SKILL.md when a user message matches. These are **system-level** skills that ship with OpenClaw — things like `weather`, `healthcheck`, and `coding-agent`.

The `.skills/paper-reading/` directory in the blog repo is something different — a **project-level** custom skill that minicat won't scan automatically. minicat's behavior is entirely driven by workspace markdown files, proactively loaded on each session start (`SOUL.md`, `BLOG_INSTRUCTIONS.md`, etc.).

So I added a "Paper Reading" section to `BLOG_INSTRUCTIONS.md`, telling minicat: what triggers the workflow, what steps to follow, and where the script lives. The `.skills/` directory is the **toolbox**; `BLOG_INSTRUCTIONS.md` is the **instruction manual** — minicat reads the manual and knows where to find the tools.

Two new trigger rules were added:

| Rose says | Behavior |
|---|---|
| arxiv link / paper PDF / "read this paper" | Enter paper reading workflow |
| Technical blog link + "write notes" | Same, in blog/documentation mode |

## Testing

Ran the full pipeline on the [SARM paper](https://arxiv.org/abs/2602.09401) (Kuaishou live-streaming ranking):

1. **Content fetch** ✅ — WebFetch grabbed arxiv abstract + HTML full text
2. **Figure extraction** ✅ — `extract_figures.py --arxiv` extracted 9 figures, selected 5 (method comparison, system architecture, gated fusion, deployment pipeline, case study)
3. **Chinese deep reading** ✅ — Complete equations, 4 experimental data tables, 5 reflections
4. **English translation** ✅ — Same structure, natural translation
5. **index.md** ✅ — Created `papers-reading/index.md`
6. **git commit** ✅

The generated notes are [[sarm-llm-livestream-ranking|here]], with figures, complete experimental data, and ablation analysis.

## Skill File Structure

```
.skills/paper-reading/
├── SKILL.md              # Full pipeline definition (documentation)
└── scripts/
    └── extract_figures.py # Figure extraction (arxiv HTML + PDF dual mode)
```

Paired with the paper reading section in `BLOG_INSTRUCTIONS.md` (minicat's call-in point): one place stores the tools, the other holds the rules.

## Takeaway

The core benefit of packaging repetitive work into a skill isn't "saving time" — a paper reading note inherently requires substantial thinking. The real value is **workflow standardization**: every run follows the same pipeline, so you never forget to extract figures, skip updating the index, or end up with structurally inconsistent bilingual versions.

Next time I want to read a paper, I just send an arxiv link.
