---
title: "MiroFish Deep Dive: When Swarm Intelligence Meets LLMs — The Logic Behind Predicting Anything"
date: 2026-03-09
updated: 2026-03-10
tags: [multi-agent, swarm-intelligence, prediction, recommendation]
lang: en
chinese: ai-news/2026-03/mirofish-swarm-intelligence
---

[中文版](./mirofish-swarm-intelligence.md)

## Why Traditional Prediction Fails

Here's a question: can you predict how a viral tweet will evolve using a statistical model?

Traditional prediction paradigms — whether time series (ARIMA, Prophet) or deep learning (LSTM, Transformer) — are fundamentally doing **pattern matching**: find patterns in historical data and extrapolate into the future. This works in the physical world (weather, tides), but often fails in **social systems**. Three reasons:

1. **Nonlinear feedback loops**: a single comment triggers millions of reposts through unpredictable pathways
2. **Individual heterogeneity**: everyone reacts differently; aggregating into an "average user" loses critical information
3. **Emergent behavior**: collective behavior ≠ sum of individual behaviors — this is the hallmark of complex systems

In other words, traditional models learn $f(\text{history}) \to \text{future}$, but the future of social systems depends on **real-time interactions between individuals**, not historical statistics.

This is exactly what MiroFish aims to solve.

## What is MiroFish

[MiroFish](https://github.com/666ghj/MiroFish) is a multi-agent AI prediction engine incubated by Shanda Group. Its core idea is intuitive:

> **Instead of predicting the future, simulate it.**

Specifically: you give MiroFish a "seed material" (news articles, novel text, policy drafts), and it automatically builds a **parallel digital world** — thousands of AI Agents with independent personalities, long-term memory, and behavioral logic interact freely within it. By observing their collective behavior, you can project how events will unfold.

### Core Innovations

| Dimension | Traditional Prediction | MiroFish |
|-----------|----------------------|----------|
| **Modeling target** | Aggregate statistics | Individual Agents + interaction network |
| **Prediction mechanism** | Pattern extrapolation | Emergent behavior simulation |
| **Input** | Structured time series | Natural language seed materials |
| **Output** | Numbers/probabilities | Prediction report + interactive digital world |
| **Interpretability** | Feature attribution | Traceable decision chain for each Agent |

MiroFish's slogan is "Predicting Anything," but more precisely, it predicts **collective behaviors that emerge from individual interactions in social systems**.

## Tech Stack Deep Dive: GraphRAG + OASIS + Zep

MiroFish's workflow has four stages, each backed by a distinct technology stack.

### Stage 1: GraphRAG for Knowledge Graph Construction

**Problem**: How do you extract structured knowledge from unstructured seed material (e.g., the first 80 chapters of *Dream of the Red Chamber*)?

MiroFish uses [GraphRAG](https://graphrag.com/reference/knowledge-graph/memory-graph-procedural/) to solve this. Unlike traditional RAG (vector retrieval), GraphRAG converts text into a **knowledge graph**:

```
Traditional RAG:
  Text → Chunking → Vectorization → Vector DB → Semantic retrieval

GraphRAG:
  Text → Entity extraction → Relation extraction → Knowledge graph → Graph traversal + Community detection
```

Why is a knowledge graph better than vector retrieval for this scenario?

- **Preserves structured relationships**: vector retrieval can only answer "what's similar to this passage"; a graph can answer "who does Jia Baoyu conflict with, and why"
- **Supports multi-hop reasoning**: Agents can reason along graph edges — A affects B, B affects C, so A indirectly affects C
- **Community discovery**: graph algorithms automatically identify factions, interest groups, and other implicit structures

In MiroFish, GraphRAG outputs include:
- **Entity nodes**: characters, organizations, events, locations
- **Relationship edges**: character relationships (allies/rivals/relatives), causal chains, temporal dependencies
- **Community structure**: auto-clustered factions/groups

This structured information is injected into each Agent's initial memory and persona.

### Stage 2: OASIS Parallel Simulation Engine

**Problem**: With knowledge graphs and Agent personas ready, how do you run thousands of Agents interacting efficiently?

MiroFish's simulation engine is powered by [OASIS](https://docs.oasis.camel-ai.org/overview) (developed by the CAMEL-AI team). OASIS was originally designed to simulate social media dynamics, supporting up to one million parallel Agents.

Key design choices in OASIS:

```
┌───────────────────────────────────────────┐
│              OASIS Architecture            │
├───────────────────────────────────────────┤
│  Agent Layer: LLM Agents + Rule-based     │
│    ↕  Message passing / Action execution  │
│  Environment Layer: Social network +      │
│    Information flow topology              │
│    ↕  State updates / Event triggers      │
│  Infrastructure: Parallel scheduling +    │
│    Temporal management                    │
└───────────────────────────────────────────┘
```

Key points:
- **Hybrid Agent architecture**: core characters use LLM (complex reasoning), background characters use rule-based Agents (cost-efficient)
- **Dynamic network topology**: social relationships between Agents evolve with interaction — relationships can form, strengthen, or break
- **Dual-platform parallel simulation**: MiroFish runs on two simulated platforms simultaneously (similar to Twitter + Reddit), observing cross-platform information propagation

This hybrid architecture is critical for cost control. If every Agent used GPT-4-level LLM, running 1000 Agents for 40 rounds would be astronomically expensive. MiroFish recommends Alibaba's qwen-plus, which costs far less than OpenAI models.

### Stage 3: Zep for Agent Memory Management

**Problem**: Agents generate massive amounts of dialogue and behavior records during interaction. How do you manage this dynamic memory?

MiroFish uses [Zep](https://www.getzep.com/) as its Agent memory management system. Zep provides:

- **Short-term memory**: recent conversation context
- **Long-term memory**: facts and relationships auto-extracted from conversations, persistently stored
- **Temporal memory**: timestamped memories supporting queries like "what happened at that time"

This resembles human memory: you don't remember every word of a conversation, but you retain key facts and emotional impressions. Zep performs **automatic summarization + structured storage**.

In the Agent memory space, alternative approaches worth noting include [Graphiti](https://medium.com/@saeedhajebi/building-ai-agents-with-knowledge-graph-memory-a-comprehensive-guide-to-graphiti-3b77e6084dec) — which uses knowledge graphs for long-term Agent memory, better capturing relationship evolution between entities.

### Stage 4: ReportAgent Generates Reports

After simulation, a dedicated ReportAgent:
1. Analyzes key events and turning points throughout the simulation
2. Deeply interacts with the simulation environment (using a rich toolkit)
3. Generates a structured prediction report

Users can continue chatting with any Agent in the simulated world or ask the ReportAgent follow-up questions.

## Workflow Case Studies

### Case 1: Predicting the Ending of *Dream of the Red Chamber*

MiroFish's most fascinating demo — predicting the lost final 40 chapters from the first 80.

```
Seed input: Full text of chapters 1-80 (hundreds of thousands of characters)
     ↓
GraphRAG builds knowledge graph:
  - Extracts 400+ character entities
  - Builds relationship network (Jia family factions, marriage ties, master-servant bonds)
  - Identifies key event chains (Grand View Garden raids → Tanchun's exile → ...)
     ↓
Agent initialization:
  - Jia Baoyu Agent: rebellious, disdains officialdom, deeply attached to Daiyu
  - Wang Xifeng Agent: shrewd, power-hungry, tense relationship with Jia Lian
  - ... Each major character gets an LLM Agent; minor characters use rule-based Agents
     ↓
OASIS simulation:
  - Inject new events (e.g., "Imperial Consort Yuanchun dies"), observe cascading reactions
  - Agents interact freely, generating new plot lines
     ↓
ReportAgent summarizes: Jia family's trajectory, character fates, key turning points
```

The significance: **this isn't text continuation** (which is just probability sampling by a language model). It's simulating social dynamics — each character makes decisions based on their personality, memory, and social relationships, and collective fates emerge.

### Case 2: Public Opinion Simulation

A more practical scenario: corporate crisis PR prediction.

```
Seed input: News report about a company's product safety incident
     ↓
GraphRAG: Extract stakeholders (company, regulators, consumers, KOLs, competitors)
     ↓
Agent initialization:
  - Angry consumer Agents (many, rule-driven)
  - KOL Agents (few, LLM-driven, with influence propagation)
  - Official spokesperson Agent
  - Regulatory body Agent
     ↓
Simulate different crisis response strategies:
  - Strategy A: Immediate apology + full recall
  - Strategy B: 24-hour silence then statement
  - Strategy C: Blame the supply chain
     ↓
Compare sentiment trajectories, propagation scale, emotional distribution across strategies
```

This is what MiroFish calls "a rehearsal lab for decision-makers."

## The Mathematical Intuition Behind Emergence

Why can multi-Agent simulation capture what single-model prediction cannot? This requires understanding the core of **Swarm Intelligence**.

### The Boids Model: Three Rules, Complex Behavior

Craig Reynolds' 1967 Boids model proved that just three simple rules can generate the complex motion of bird flocks:

```
Separation: avoid getting too close to neighbors
Alignment: move toward neighbors' average direction
Cohesion: move toward neighbors' average position
```

Each individual sees only local information, but globally coordinated behavior emerges. **No central controller.**

### Why N Agents > 1 Strong Model

Intuitively:

A single model prediction finds a function $f$:

$$\hat{y} = f(x; \theta)$$

where $\theta$ is learned from training data. The model's ceiling depends on the training data distribution.

Multi-Agent simulation is a dynamical system:

$$s_i^{t+1} = g(s_i^t, \{s_j^t\}_{j \in \mathcal{N}(i)}, \epsilon_i^t)$$

where $s_i^t$ is Agent $i$'s state at time $t$, $\mathcal{N}(i)$ are its neighbors, and $\epsilon_i^t$ is stochastic perturbation.

The key difference:
- **Single model**: one forward pass, input to output
- **Multi-Agent**: iterative interaction, each step's output feeds the next, allowing **feedback loops** and **nonlinear amplification**

This means multi-Agent systems can produce behavioral patterns **never seen in training data** — that's emergence.

An analogy: a single model is like watching 1,000 recorded chess games and predicting the next move; a multi-Agent system is like having Agents actually play chess, where every move can create positions never seen in any playbook.

### Information-Theoretic Perspective

From an information theory standpoint, $N$ heterogeneous Agents' joint state space far exceeds a single model's output space:

$$H(S_1, S_2, ..., S_N) \gg H(Y_{\text{single model}})$$

Because conditional dependencies between Agents ($S_i \not\perp S_j \mid S_k$) create a combinatorial explosion of possibilities. This is both multi-Agent's strength (expressive power) and challenge (computational cost, result variance).

## Deep Implications for Recommendation Systems

As someone studying recommender systems, MiroFish offered me three important insights.

### Insight 1: From CTR Prediction to User Ecosystem Simulation

Traditional recommendation = predicting $P(\text{click} \mid \text{user}, \text{item})$. But users aren't isolated — they influence each other:

- Items recommended by friends are more likely to be clicked
- KOLs' choices shape followers' preferences
- Group trends (trending) influence individual behavior

MiroFish's approach: **don't predict individual behavior; simulate group interaction and let recommendations emerge from the dynamics**.

This aligns with [AgentRec](https://arxiv.org/html/2510.01609) (2025), which uses multiple Agents to collaboratively recommend — one for dialogue understanding, one for preference modeling, one for context awareness, one for dynamic ranking. Each Agent focuses on a subtask; collaboration produces better recommendations through emergence.

### Insight 2: Using Agents for Counterfactual Reasoning

A classic challenge in recommender systems is **counterfactual evaluation**: what would happen if I recommended a different item?

MiroFish's simulation framework naturally supports this: create multiple parallel worlds, recommend different content in each, and observe user Agents' subsequent behavior. More intuitive than traditional IPS (Inverse Propensity Scoring) and doubly robust estimators, though significantly more computationally expensive.

### Insight 3: Joint Modeling of Social Networks + Recommendations

MARL4CDSR (Multi-Agent Reinforcement Learning for Cross-Domain Sequential Recommendation) already explores using multi-Agent for cross-domain recommendation. MiroFish's OASIS engine goes further — it simulates **information propagation dynamics in social networks**.

Imagine: your recommender system doesn't just predict "will user A click," but simulates "after recommending to A, will A share with B, will B repost and trigger viral spread" — this is a paradigm shift from **individual recommendation** to **network recommendation**.

```
Traditional: user → model → item (one-to-one prediction)
Network: user_network → multi-agent_sim → cascade_prediction (considering propagation effects)
```

## Practical Deployment Advice

### Deployment

MiroFish offers Docker and source code deployment. Requirements:
- Node.js 18+ (frontend)
- Python 3.11-3.12 (backend)
- Two API keys: LLM (Alibaba's qwen-plus recommended) + Zep Cloud

### Cost Control

This needs the most attention. Official docs explicitly state "consumption is significant; try simulations under 40 rounds first."

Rough estimates:
- Core Agents use LLM (~500-1000 tokens per Agent per round)
- Background Agents use rule engines (no LLM cost)
- 40 rounds × 50 LLM Agents ≈ 1-2 million tokens
- Using qwen-plus: approximately ¥10-20 (~$1.5-3) per simulation

Cost control strategies:
1. **Minimize LLM Agent count**: only key characters get LLM; others use rule-based Agents
2. **Control simulation rounds**: start with 20 rounds to gauge trends, then extend
3. **Choose cost-effective LLMs**: qwen-plus is far cheaper than GPT-4

### Common Pitfalls

1. **Agent persona collapse**: after many rounds, Agents may "forget" their initial persona. Zep's memory management partially mitigates this, but long-term simulation remains challenging
2. **Non-reproducible results**: LLM randomness + chaotic multi-Agent dynamics = different results every run. Run multiple simulations and look for consensus
3. **Seed material quality**: garbage in, garbage out. If seed materials lack sufficient information, Agents will hallucinate extensively

## My Take

### Opportunities

MiroFish represents an important paradigm shift: **from statistical prediction to causal simulation**. It's not mining patterns from historical data; it's building a causal world and letting events "naturally occur." This has enormous potential in policy evaluation, crisis PR, and social science research.

Architecturally, it cleverly combines three mature components: GraphRAG (knowledge structuring), OASIS (parallel simulation), and Zep (memory management). None are new individually, but together they form a complete prediction engine. This "combinatorial innovation" is engineering elegance in itself.

### Challenges

1. **Validation**: How do you verify simulation results? The *Red Chamber* "prediction" can't be falsified (the true ending is lost), and crisis simulations are hard to test with controlled experiments
2. **Scale bottleneck**: Real social systems involve millions of people; current LLM Agents face cost pressure at the thousand-Agent scale
3. **Missing evaluation metrics**: Traditional prediction has MAE, RMSE, AUC; what's the evaluation standard for multi-Agent simulation? The field hasn't reached consensus yet
4. **Emergence ≠ correctness**: Agent systems will produce emergent behaviors, but emergent behaviors don't necessarily reflect reality. Model biases get amplified

Overall, MiroFish is a highly inspiring project. It probably won't replace traditional prediction (they serve different use cases), but it opens a window: **when LLMs become cheap and powerful enough, social simulation will become an entirely new way of understanding the world.**

## References

- [MiroFish GitHub](https://github.com/666ghj/MiroFish)
- [OASIS Documentation](https://docs.oasis.camel-ai.org/overview)
- [AgentRec Paper](https://arxiv.org/html/2510.01609)
- [GraphRAG Documentation](https://graphrag.com/reference/knowledge-graph/memory-graph-procedural/)
- [Zep - AI Agent Memory](https://www.getzep.com/)
- [Graphiti: Agent Memory with Knowledge Graphs](https://medium.com/@saeedhajebi/building-ai-agents-with-knowledge-graph-memory-a-comprehensive-guide-to-graphiti-3b77e6084dec)
