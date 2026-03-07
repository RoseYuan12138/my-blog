---
title: "Teaching the AI Butler a New Skill: Paper Reading"
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

With the [[openclaw-blog-workflow|blog butler]] already set up, minicat can draft notes, translate, and commit to git. But reading papers was still entirely manual — fetch the paper, extract figures, write bilingual notes, update the index, commit — a fixed process with many steps. So I decided to codify this workflow into a reusable skill.

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

Here's the key challenge: **Cowork's `.skill` file mechanism and OpenClaw's instruction system are two completely different things**.

Cowork (Claude's desktop app) triggers skills via the description field in SKILL.md's YAML frontmatter — essentially injecting the skill description into Claude's available tools list.

OpenClaw's minicat relies entirely on markdown files in its workspace for instructions. On each session start, it reads `SOUL.md` (identity), `BLOG_INSTRUCTIONS.md` (blog operation guide), and other files.

So the same skill needs **two entry points**:

1. **`.skills/paper-reading/SKILL.md`**: For Cowork — contains the full pipeline description and script paths, lives in the blog repo
2. **"Paper Reading" section in `BLOG_INSTRUCTIONS.md`**: For minicat — written into its behavior guide with trigger words, workflow, directory mapping, and article template

Both reference the same `extract_figures.py` script, keeping the tooling layer unified.

Two new trigger rules were added to the trigger word table in `BLOG_INSTRUCTIONS.md`:

| Rose says | Behavior |
|---|---|
| arxiv link / paper PDF / "read this paper" | Enter paper reading workflow |
| Technical blog link + "write notes" | Same, in blog/documentation mode |

## Testing

Ran the full pipeline on the [SARM paper](https://arxiv.org/abs/2602.09401) (Kuaishou live-streaming ranking):

1. **Content fetch** ✅ — WebFetch grabbed arxiv abstract + HTML full text
2. **Figure extraction** ✅ — `extract_figures.py --arxiv` extracted 9 figures, selected 3 (architecture, method comparison, SAE details)
3. **Chinese deep reading** ✅ — Complete equations, 4 experimental data tables, 5 reflections
4. **English translation** ✅ — Same structure, natural translation
5. **index.md** ✅ — Created `papers-reading/index.md`
6. **git commit** ✅

The generated notes are [[sarm-llm-livestream-ranking|here]], with figures, complete experimental data, and ablation analysis.

## Skill File Structure

```
.skills/paper-reading/
├── SKILL.md              # Pipeline definition (Cowork entry point)
└── scripts/
    └── extract_figures.py # Figure extraction (arxiv HTML + PDF dual mode)
```

Together with the paper reading section in `BLOG_INSTRUCTIONS.md` (minicat entry point), three files define and distribute the entire skill.

## Takeaway

The core benefit of packaging repetitive work into a skill isn't "saving time" — a paper reading note inherently requires substantial thinking. The real value is **workflow standardization**: every run follows the same pipeline, so you never forget to extract figures, skip updating the index, or end up with structurally inconsistent bilingual versions.

Next time I want to read a paper, I just send an arxiv link.
