---
title: "MiroFish: A Swarm Intelligence Prediction Engine — From Prediction to Pre-Enactment"
date: 2026-03-09
updated: 2026-03-10
tags:
  - multi-agent
  - swarm-intelligence
  - prediction-engine
  - recommendation-systems
lang: en
chinese: ai-news/2026-03/mirofish-swarm-intelligence
---

> 阅读[中文版](mirofish-swarm-intelligence.md)

## Why Traditional Prediction Fails

Traditional prediction — time series (ARIMA, Prophet) or deep learning (LSTM, Transformer) — is fundamentally **pattern matching**: find regularities in historical data, extrapolate to the future. This works for physical systems but often fails in **social systems**:

1. **Nonlinear feedback loops**: one viral comment triggers millions of reposts
2. **Individual heterogeneity**: averaging users erases critical information
3. **Emergence**: collective behavior ≠ sum of individual behaviors

Traditional models learn $f(\text{history}) \to \text{future}$, but social outcomes depend on **real-time interactions between individuals**. This is what MiroFish aims to solve.

## What Is MiroFish

[MiroFish](https://github.com/666ghj/MiroFish) is a multi-agent AI prediction engine incubated and strategically backed by Shanda Group, with ¥30 million in funding. It topped GitHub Trending in March 2026, reflecting the AI community's keen interest in multi-agent social simulation. Core idea:

> **Instead of predicting the future, simulate it.**

Feed MiroFish seed materials (news, novels, policy drafts) → it builds a **parallel digital world** with thousands of AI Agents, each with independent personality, long-term memory, and behavioral logic → observe their collective behavior to extrapolate outcomes.

| Dimension | Traditional Prediction | MiroFish |
|-----------|----------------------|----------|
| **Models** | Aggregate statistics | Individual Agents + interaction network |
| **Mechanism** | Pattern extrapolation | Emergent simulation |
| **Input** | Structured time-series | Natural language seed materials |
| **Output** | Numbers / probabilities | Prediction report + interactive digital world |

## Workflow

```
Seed Materials (news / policy / novel / financial reports)
    ↓
① GraphRAG builds knowledge graph → extracts entities & relations
    ↓
② Environment setup → independent Agent per entity (persona, goals, logic)
    ↓
③ OASIS simulation → dual-platform parallel run → Agents converse, decide, conflict
    ↓
④ ReportAgent generates structured prediction report
    ↓
⑤ User can chat with any Agent in the simulated world
```

### Example: Predicting How Dream of the Red Chamber Ends

Using the first 80 chapters to predict the lost ending — not text continuation, but social dynamics simulation:

- GraphRAG extracts 400+ character entities and relationship networks
- Each major character gets an LLM Agent (Jia Baoyu: rebellious, disdains officialdom, deeply attached to Lin Daiyu); minor characters use rule-based Agents
- Inject new events (death of Imperial Consort Yuan), observe cascading reactions
- Each character decides based on their own personality, memory, and social ties → collective fate **emerges**

**Full demonstration video**: [Predicting the Lost Ending of Dream of the Red Chamber (Bilibili)](https://www.bilibili.com/video/BV1cPk3BBExq/) — see how MiroFish lets thousands of character Agents freely interact and pre-enact a complete storyline ending.

## Theoretical Foundation: Swarm Intelligence

MiroFish's core bet: **swarm intelligence produces predictive power that no single model can achieve**. The theory is solid.

### What Is Swarm Intelligence

Swarm Intelligence refers to decentralized, self-organizing individuals producing complex global behavior through simple **local rules**. No central controller, no global blueprint — complexity grows from the bottom up.

Craig Reynolds' **Boids model** (1986) demonstrated that just three rules generate complex flocking behavior:

- **Separation**: avoid crowding nearby neighbors
- **Alignment**: steer towards the average heading of neighbors
- **Cohesion**: move toward the average position of neighbors

Each individual only sees local information, yet globally the flock exhibits coordinated obstacle avoidance, formation flying, and stream splitting.

### Why N Agents > 1 Strong Model

**Single Agent limitation**: essentially one forward pass $\hat{y} = f(x; \theta)$, bounded by training data distribution. For out-of-distribution social events, it can only extrapolate linearly — easily trapped in local optima.

**Multi-Agent advantage**: an iterative dynamical system $s_i^{t+1} = g(s_i^t, \{s_j^t\}_{j \in \mathcal{N}(i)}, \epsilon_i^t)$ — each step's output feeds the next, enabling feedback loops and nonlinear amplification. The joint state space of $N$ heterogeneous Agents far exceeds any single model's output space, producing behavior patterns **never seen in training data**.

Intuitive examples:
- **Bird flocks** vs **a single bird**: flocks coordinate predator evasion — an emergent capability no individual possesses
- **Financial markets**: retail investor panic selling / FOMO buying isn't predictable by any single analyst — crowd behavior has its own dynamics

MiroFish leverages this: Agents "actually play the game" in the simulated world, potentially producing moves beyond any playbook, rather than one model "guessing the next move after watching 1,000 recorded games."

## Tech Stack at a Glance

| Component | Role | Notes |
|-----------|------|-------|
| **GraphRAG** | Build knowledge graph from text, extract entity relationships | Structured context for Agents |
| **OASIS** | CAMEL-AI open-source simulation engine, supports up to 1M parallel Agents | Simulation core |
| **Zep** | Agent long-term memory management (short-term / long-term / temporal) | Free tier sufficient |
| **ReportAgent** | Interacts with post-simulation world, generates structured reports | Output layer |

Deployment: Node.js 18+ frontend, Python 3.11-3.12 backend, Docker Compose one-click setup. Recommended LLM: Qwen-plus (Alibaba Cloud).

## Technical Deep Dive & Comparative Research

### GraphRAG: Why Better Than Pure Vector Retrieval

Traditional RAG chunks text and vectorizes it — it can only answer "what's most similar to this passage." GraphRAG converts text into a **knowledge graph** — entities as nodes, relationships as edges:

- **Preserves structured relationships**: extracts "Lin Daiyu →(rivalry)→ Xue Baochai" as a semantic relation, not just vector similarity between their names
- **Multi-hop reasoning**: A influences B, B influences C, therefore A indirectly influences C
- **Community detection**: graph algorithms automatically identify factions and interest groups

Comparable tools: [Graphiti](https://medium.com/@saeedhajebi/building-ai-agents-with-knowledge-graph-memory-a-comprehensive-guide-to-graphiti-3b77e6084dec) (knowledge-graph-based Agent memory), [Cognee](https://github.com/topoteretes/cognee) (open-source cognitive memory engine with hybrid graph + vector retrieval). Each has a different focus: GraphRAG → knowledge structuring, Graphiti → Agent memory, Cognee → hybrid retrieval pipelines.

### OASIS Simulation Engine

[OASIS](https://docs.oasis.camel-ai.org/overview), built by the CAMEL-AI team, was originally designed for social media dynamics simulation, supporting up to **1 million parallel Agents**. Why MiroFish chose OASIS:

- **Scalability**: smooth scaling from dozens to millions of Agents
- **Native LLM integration**: core roles use LLM Agents, background crowd uses rule-based Agents (key for cost control)
- **Dynamic network topology**: social relationships evolve with interactions — can form, strengthen, or break
- **Dual-platform parallel execution**: simulates two social platforms simultaneously, observing cross-platform information propagation

### Comparative Frontier Research

**[AgentRec](https://arxiv.org/html/2510.01609) (2025)**: the latest paradigm for multi-agent recommendation systems. It decomposes recommendation into specialized collaborating Agents — dialogue understanding, preference modeling, context awareness, dynamic ranking — each handling one pipeline stage, then fusing decisions. vs. MiroFish: AgentRec's Agents are **functionally specialized** (each handles a step in the recommendation pipeline); MiroFish's Agents are **role-playing** (each simulates a real individual).

**MARL4CDSR (2025)**: multi-agent reinforcement learning for cross-domain sequential recommendation. Uses RL Agents to coordinate recommendation strategies across domains (movies, music, e-commerce). Shared with MiroFish: multi-agent architecture. Difference: MARL4CDSR optimizes cross-domain transfer efficiency; MiroFish optimizes social dynamics fidelity.

These three represent three routes for multi-agent approaches in recommendation/prediction: **functional collaboration** (AgentRec), **strategy coordination** (MARL4CDSR), **social simulation** (MiroFish).

## Insights for Recommendation Systems

### From CTR Prediction to User Ecosystem Simulation

Traditional recommendation predicts $P(\text{click} \mid \text{user}, \text{item})$, but users aren't isolated — friends' recommendations carry more weight, KOLs shape follower preferences, trends shape individual behavior. MiroFish's approach: **don't predict individual behavior; simulate group interaction and let recommendations emerge**.

### Counterfactual Reasoning via Agents

A classic recommender challenge: what if we had recommended a different item? MiroFish's simulation framework naturally supports this — create parallel worlds with different recommendations, observe Agent behavior downstream. More intuitive than IPS / doubly robust estimators, though computationally heavier.

### Joint Modeling of Social Networks + Recommendations

Imagine a recommender that doesn't just predict "will User A click" but simulates "after recommending to A, will A share with B, will B repost and go viral" — a paradigm shift from **individual recommendation** to **network recommendation**.

## Practical Advice

- **Cost control**: 40 rounds × 50 LLM Agents ≈ 1M-2M tokens. With qwen-plus: ~¥10-20/simulation. Start with 20 rounds to gauge trends
- **Common pitfalls**: Agent persona drift (long simulations), non-reproducible results (LLM stochasticity + chaotic multi-agent interactions), seed material quality determines output quality

## Personal Take

MiroFish represents a paradigm shift **from statistical prediction to causal simulation**. It cleverly combines GraphRAG (knowledge structuring) + OASIS (parallel simulation) + Zep (memory management) — none are new individually, but together they form a complete prediction engine.

Challenges are real: simulation results are hard to validate (the Red Chamber prediction can't be falsified), scale bottlenecks (cost pressure at thousands of Agents), missing evaluation metrics (what's "accuracy" for multi-agent simulation?). Emergence ≠ correctness — model biases get amplified.

But the direction is worth watching: **when LLMs become cheap and powerful enough, social simulation will become an entirely new way to understand the world.**

## References

- [MiroFish GitHub](https://github.com/666ghj/MiroFish)
- [OASIS Documentation](https://docs.oasis.camel-ai.org/overview)
- [AgentRec Paper](https://arxiv.org/html/2510.01609)
- [GraphRAG Documentation](https://graphrag.com/reference/knowledge-graph/memory-graph-procedural/)
- [Zep - AI Agent Memory](https://www.getzep.com/)
- [Graphiti: Agent Memory with Knowledge Graphs](https://medium.com/@saeedhajebi/building-ai-agents-with-knowledge-graph-memory-a-comprehensive-guide-to-graphiti-3b77e6084dec)
- [Cognee - Open Source Cognitive Memory](https://github.com/topoteretes/cognee)
