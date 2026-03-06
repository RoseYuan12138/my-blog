---
name: paper-reading
description: |
  Turn academic papers or technical articles into structured blog posts with extracted figures.
  MANDATORY TRIGGERS: arxiv link, paper URL, PDF paper upload, "读一下这篇", "这篇论文", "paper", "论文笔记",
  technical blog URL for note-taking, "写个笔记", "总结一下这篇文章".
  Also trigger when the user pastes a paper's content and asks to turn it into a blog post.
  This skill handles the full pipeline: fetch content → extract figures from PDF → write bilingual blog posts → commit.
---

# Paper Reading → Blog Post

Turn academic papers and technical articles into structured, bilingual blog posts with figures.

## When This Skill Activates

Any time the user shares a paper or technical article for blog conversion:
- An arxiv link (e.g., `https://arxiv.org/abs/XXXX.XXXXX`)
- A PDF file upload
- A technical blog / documentation URL
- Pasted paper content with intent to blog it

## Overview of the Pipeline

```
Input (arxiv link / PDF / blog URL / pasted content)
  ↓
1. Fetch & read the full content
2. Extract figures from PDF (if available)
3. Write Chinese blog post (primary)
4. Write English translation
5. Update index.md
6. Git commit (but NOT push)
```

## Step 0: Read Blog Conventions

Before writing anything, read the blog's instruction file to ensure the output conforms to established conventions:

```
Read: BLOG_INSTRUCTIONS.md (from the blog workspace or uploads)
```

This file defines frontmatter format, directory structure, bilingual rules, writing style, and git workflow. Everything below builds on top of those conventions.

## Step 1: Fetch the Content

### For arxiv papers

1. Fetch the abstract page: `https://arxiv.org/abs/XXXX.XXXXX`
2. Fetch the HTML version for full text: `https://arxiv.org/html/XXXX.XXXXX`
3. If HTML isn't available, fetch the PDF: `https://arxiv.org/pdf/XXXX.XXXXX`
4. Extract: title, authors, affiliation, abstract, all sections, equations, tables, experimental results

When fetching, be thorough — make multiple WebFetch calls with specific prompts to capture all technical details: methodology, architecture, equations, experimental setup, results tables, ablation studies, and conclusions.

### For uploaded PDFs

Use the Read tool to read the PDF. For long papers (>10 pages), read in page ranges.

### For technical blog posts / documentation

WebFetch the URL and extract the key content.

## Step 2: Extract Figures

Figures are critical for making paper reading notes visually informative. Always include the most important figures — typically the architecture diagram and key result visualizations.

### For arxiv papers (preferred: HTML extraction)

arxiv HTML versions contain complete, high-quality rendered figures. This is much better than PDF extraction, which often fragments composite figures into individual embedded images (e.g., photos within a figure grid rather than the complete figure).

```bash
# Install PyMuPDF if needed (for PDF fallback)
pip install PyMuPDF --break-system-packages 2>/dev/null

# Extract from arxiv HTML (preferred)
python .skills/paper-reading/scripts/extract_figures.py --arxiv XXXX.XXXXX --output /tmp/paper-figures/
```

The script downloads figures named `x1.png`, `x2.png`, etc. from the arxiv HTML version and saves them as `figure-1.png`, `figure-2.png`, etc. with a `manifest.json`.

If the arxiv HTML version doesn't exist (older papers), fall back to PDF extraction:

```bash
curl -L -o /tmp/paper.pdf "https://arxiv.org/pdf/XXXX.XXXXX"
python .skills/paper-reading/scripts/extract_figures.py --pdf /tmp/paper.pdf --output /tmp/paper-figures/
```

After extraction, **visually inspect each figure** using the Read tool to understand what it shows and decide which to include.

### For uploaded PDFs (non-arxiv)

```bash
python .skills/paper-reading/scripts/extract_figures.py --pdf /path/to/uploaded.pdf --output /tmp/paper-figures/
```

Note: PDF extraction pulls raw embedded images, which may not be complete figures. Visually verify each one.

### Selecting and Naming Figures

After extraction, select the most valuable figures for the blog post. Typically include:
- **Architecture / system overview diagram** (almost always Figure 1 or 2 in the paper)
- **Key results visualization** (performance comparison charts, attention maps, etc.)
- **Any diagram that explains a novel mechanism** (tiling strategy, data flow, etc.)

Skip: redundant variations of the same chart, tiny logos, watermarks, simple bar charts that are better expressed as tables.

Rename selected figures with descriptive names:

```bash
# Examples of good naming:
cp /tmp/paper-figures/figure-1.png content/<domain>/papers-reading/assets/sarm-architecture.png
cp /tmp/paper-figures/figure-3.png content/<domain>/papers-reading/assets/sarm-attention-visualization.png
```

Naming convention: `<paper-short-name>-<what-it-shows>.<ext>`

### For technical blogs (no PDF)

If the source is a web article with inline images, download the relevant images directly. If no images are available, skip this step — don't generate placeholder images.

## Step 3: Determine Blog Location

Auto-assign the directory based on the paper's domain:

| Paper Domain | Blog Directory |
|---|---|
| Recommender systems, ranking, CTR, user modeling | `recommender-systems/papers-reading/` |
| Transformers, attention, LLM architecture | `machine-learning/papers-reading/` |
| Training techniques, optimization, debugging | `machine-learning/papers-reading/` |
| AI agents, multi-agent, tool use | `ai-agent/papers-reading/` |
| Other / new domain | `<domain>/papers-reading/`, ask user if unsure |

The file name should be: `<short-descriptive-name>.md` (Chinese) and `<short-descriptive-name>.en.md` (English).

Use lowercase + hyphens. Derive from the paper's key contribution, not just the acronym. For example:
- Good: `sarm-llm-livestream-ranking.md`
- Bad: `sarm.md` (too vague)
- Bad: `sarm-llm-augmented-semantic-anchor-for-end-to-end-live-streaming-ranking.md` (too long)

## Step 4: Write the Chinese Blog Post (Primary)

### Default Style: 论文精读 (Paper Deep-Dive)

Write a thorough reading note that someone in the field can learn from without reading the original paper. This is the default — use it unless the user explicitly asks for something lighter.

### Article Structure

```markdown
---
title: "<中文简短标题>"
date: YYYY-MM-DD
tags:
  - <中文 tag 1>
  - <中文 tag 2>
lang: zh
english: <path-to-english-version-without-.md>
---

> 🌐 [Read in English](./<filename>.en.md)

论文精读笔记：[<Paper Title>](<arxiv-url>)（<affiliation>，<year>）

## 核心思路

[2-3 sentences: what problem, what solution, why it's different from prior work]

## 系统架构 / 方法

[Architecture overview with ASCII diagram or reference to figure]
[Include the architecture figure here if extracted]

![架构概览](./assets/<figure-name>.png)

[Break down into subsections for each major component]
[Include ALL key equations with LaTeX: $inline$ and $$block$$]
[Explain the intuition behind each equation — don't just list formulas]

## 训练目标 / 损失函数

[Loss functions with full LaTeX]
[Explain WHY each loss term exists, not just what it computes]

## 实验结果

[Reproduce key results tables in markdown]
[Include ALL numbers from the most important comparison table]
[Call out the most interesting observations — what's surprising, what confirms intuition]

### Ablation 分析

[Key ablation results — which components matter most and why]

### 线上实验 (if applicable)

[Online A/B test results]

## 值得思考的点

[3-5 reflections: limitations, open questions, connections to other work, potential improvements]
[This section is what makes it a "reading note" rather than a summary — it's YOUR thinking]

## 参考

- [Paper Title](arxiv-url)
- [Other referenced papers with real URLs]
```

### Writing Principles

The goal is a **learning note** — you're explaining the paper to a future version of yourself (or a colleague). Key principles:

- **Explain the "why" before the "what"**: Before showing an equation, explain what problem it solves and what the intuition is. The equation is the formalization, not the explanation.
- **Don't just summarize — analyze**: The "值得思考的点" section at the end should contain genuine reflections: limitations the authors don't discuss, connections to other papers, potential extensions, things you're skeptical about.
- **Reproduce key data faithfully**: Copy experimental numbers exactly from the paper. Don't round or paraphrase quantitative results.
- **Use ASCII diagrams for system overviews**: A simple text flow diagram (like `A → B → C`) often communicates architecture better than words alone, especially when the figure hasn't been extracted yet.
- **LaTeX for all math**: Use `$...$` for inline and `$$...$$` for block equations. Keep notation consistent with the paper.

### Style Overrides

The user can override the default style with casual instructions:

| User says | Behavior |
|---|---|
| Default (no override) | Full 精读: all equations, all tables, reflections |
| "简单总结一下" / "quick summary" | 1-page summary: core idea, key result, 1-2 takeaways. Skip equations and detailed tables |
| "重点讲讲 [aspect]" | Focus the deep-dive on a specific aspect (e.g., "重点讲讲 loss design") |

## Step 5: Write the English Translation

Create the `.en.md` version following the blog's bilingual conventions:

- Same structure and depth as the Chinese version
- Natural English, not word-for-word translation
- Keep all code blocks, equations, and figure references identical
- Technical terms in English (no need to translate jargon)
- Use English tags in frontmatter

## Step 6: Update index.md

Add a wikilink entry to the corresponding `index.md` file. If the index doesn't have a description yet, add one.

## Step 7: Git Commit (NOT Push)

Stage and commit following the blog's git conventions:

```bash
git add <new-files> <updated-index>
git commit -m "add: <paper-short-name> 论文精读笔记（中英双语）"
```

**Never push** — wait for the user to say "push".

## Checklist Before Finishing

- [ ] Frontmatter follows BLOG_INSTRUCTIONS.md format exactly (title, date, tags, lang, english/chinese)
- [ ] Language toggle link at the top of both versions
- [ ] All equations use LaTeX (`$...$` / `$$...$$`)
- [ ] All reference links are real and point to actual URLs (arxiv, ACM DL, etc.)
- [ ] Figures are in the correct `assets/` directory with descriptive names
- [ ] Figure references use relative paths (`./assets/<name>.png`)
- [ ] Key experimental results are reproduced faithfully with exact numbers
- [ ] index.md is updated
- [ ] Committed but NOT pushed
