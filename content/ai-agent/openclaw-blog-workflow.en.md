---
title: "Managing a Personal Knowledge Base Blog with OpenClaw"
date: 2026-03-01
tags:
  - AI Agent
  - OpenClaw
  - workflow
lang: en
chinese: ai-agent/openclaw-blog-workflow
---

> 🌐 [中文版](./openclaw-blog-workflow.md)

## Background

I have a personal blog built on Quartz v4 (hosted on GitHub Pages), and I wanted a workflow where I could send whatever I learned each day to an AI, and have it organize everything into structured knowledge base articles and keep the blog updated.

I chose OpenClaw because it runs locally, stays in the background, and communicates through chat apps — a natural fit for a "knowledge editor assistant."

## Three Core Problems to Solve

### 1. Teach the bot how to update the blog

The bot needs technical context — otherwise it has no idea where files go or what format to use.

**Solution**: write a `BLOG_INSTRUCTIONS.md` in the OpenClaw workspace covering:

- Local repo path and branch (`v4`)
- Content directory structure rules (`content/[domain]/[subdomain]/article.md`)
- Quartz frontmatter format (title, date, tags, lang, etc.)
- Bilingual rules (Chinese primary `.md` + English translation `.en.md`)
- Git workflow (add → commit → push, **never auto-push**)
- Explicit list of forbidden actions (don't touch config files, don't delete existing articles, don't make things up)

The key insight: treat this file as the bot's operations manual, and reference it in `SOUL.md` so the bot reads it before handling any blog-related task.

### 2. Define the bot's behavior

Technical knowledge alone isn't enough — the bot also needs to know *when* to act and *how* to write.

**Solution**: write a `WRITING_GUIDE.md` with:

**Trigger word system** — map chat keywords to actions:

| I say | Bot does |
|---|---|
| `note:...` | Draft a blog post |
| `publish:...` | Draft and prepare for publishing |
| `update [article]:...` | Append new content to existing article |
| `translate [article]` | Generate English version |
| No trigger word | Normal chat — don't auto-write articles |

**Writing style guidelines**:
- Study notes style: concise and direct, don't over-polish
- Every article needs: core concept, key points, code/examples (if any), references
- Mark uncertain content with `[TODO]`, never fabricate

### 3. Review and revision flow

I chose the lightest option — review directly in chat:

```
Rose sends content → bot drafts article → sends preview in chat
→ Rose says "OK" → bot saves + generates English version → Rose skims English
→ confirms → bot runs git push → published
```

If I want changes, I just say "fix [specific thing]" and the bot resends the full revised article.

Upside: zero extra tools. Downside: no revision history. If a more formal flow is needed later, we can switch to PR-based review.

## Setup Steps

### 1. Place instruction files in the OpenClaw workspace

On macOS, the workspace directory starts with `.` so it's hidden by default. In Finder, press `Cmd + Shift + .` to show hidden files, or use `Cmd + Shift + G` to navigate directly to the path.

### 2. Reference them in SOUL.md

Add a section to `SOUL.md`: before handling any blog-related task, read `BLOG_INSTRUCTIONS.md` and `WRITING_GUIDE.md`.

### 3. Make sure the bot can access the blog repo

The bot needs read/write access to the local clone, and git must be configured with push credentials.

## Knowledge Base Directory Design

Since the knowledge base will grow into new domains over time, the directory structure needs to stay flexible. Simple rules:

- Folder names in lowercase with hyphens
- Each folder has an `index.md` overview
- Split into subdirectories only when a domain has 3+ articles in different directions
- The bot periodically checks whether the structure needs reorganization

## Bilingual Setup

Quartz v4 doesn't natively support article-level language toggle buttons, so I used a simple approach:

- Two files per article: `article.md` (Chinese) + `article.en.md` (English)
- A link at the top of each version pointing to the other
- `lang` and `english`/`chinese` fields in frontmatter to mark the relationship
- After writing the Chinese version, the bot automatically translates and generates the English version

For a proper language-toggle button in the UI, you'd need a custom Quartz TypeScript component.

## Summary

The core idea: **write all the rules as documents and let the bot read them**. Don't try to explain everything verbally in one conversation — the bot will forget. Persist the instructions as files, and the bot can always reference them.

Two key files:
- `BLOG_INSTRUCTIONS.md`: technical layer — how to operate
- `WRITING_GUIDE.md`: behavior layer — how to write, how to review
