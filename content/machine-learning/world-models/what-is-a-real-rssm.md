---
title: "什么才是完整的 RSSM？从 deterministic GRU 到随机状态空间模型"
date: 2026-08-23
tags:
  - RSSM
  - World Models
  - Model-Based RL
  - Dreamer
  - Variational Inference
lang: zh
---

在世界模型的实现中，经常能看到一段 GRU：输入上一步状态和动作，递归地产生下一个 hidden state。它看起来很像 RSSM（Recurrent State-Space Model），但**只有 deterministic GRU，并不等于 PlaNet / Dreamer 语境中的完整 RSSM**。

这类实现可以叫“确定性循环动力学模型”或“简化版 RSSM”，但如果没有 stochastic state、prior / posterior distribution 和 KL loss，就失去了 RSSM 最关键的概率建模部分。

> 更严谨地说，RSSM 在不同文献中并没有唯一实现。本文讨论的是 PlaNet、Dreamer 系列采用的 variational RSSM；在这个语境下，确定性 GRU 只是 RSSM 的一个组成部分。

## 一、完整 RSSM 的状态由两部分组成

RSSM 的 latent state 通常写成：

$$
s_t = (h_t, z_t)
$$

- $h_t$：**deterministic state**，通常由 GRU 更新，负责压缩历史信息。
- $z_t$：**stochastic state**，从一个概率分布中采样，用来表达当前时刻的不确定性和多种可能未来。

确定性状态的典型更新是：

$$
h_t = f_\theta(h_{t-1}, z_{t-1}, a_{t-1})
$$

注意，GRU 不只是接收旧的 hidden state 和 action；上一时刻采样出的 stochastic state $z_{t-1}$ 也参与递归更新。因此，GRU 是 RSSM 的“记忆骨架”，而不是整个 RSSM。

## 二、同一个 stochastic state，需要 prior 和 posterior 两套分布

RSSM 在每个时间步维护两种对 $z_t$ 的预测。

### 2.1 Prior：不看当前观测，预测未来

$$
p_\theta(z_t \mid h_t)
$$

prior 只依赖动力学已经递推得到的 $h_t$，不读取当前观测 $o_t$。它回答的是：

> 只根据过去和动作，我认为下一状态可能是什么？

训练完成后做 imagination rollout 时，未来真实观测不存在，模型只能从 prior 采样。因此，**真正承担“想象未来”任务的是 prior dynamics**。

### 2.2 Posterior：看过当前观测后，推断状态

先把观测编码为特征：

$$
e_t = \operatorname{Encoder}_\phi(o_t)
$$

再得到 posterior：

$$
q_\phi(z_t \mid h_t, e_t)
$$

posterior 回答的是：

> 结合我刚看到的真实观测，当前 latent state 更可能是什么？

训练时通常从 posterior 采样 $z_t$，让表示吸收真实观测的信息。连续版本可以输出高斯分布的均值和标准差；DreamerV2 / V3 一类实现则常使用多组 categorical latent variables。分布形式可以变化，但“可采样的 stochastic state + prior / posterior”这套结构不应消失。

## 三、KL loss 把“看过答案”和“闭眼预测”对齐

有了两套分布，还需要让 prior 学会逼近 posterior：

$$
\mathcal{L}_{\mathrm{KL}}
= D_{\mathrm{KL}}\left[
q_\phi(z_t \mid h_t,e_t)
\;\|\;
p_\theta(z_t \mid h_t)
\right]
$$

可以把 posterior 理解为“看过当前画面后的老师”，prior 是“只根据历史预测的学生”。KL divergence 将学生的预测分布拉向老师的推断分布。

如果没有这项约束，训练时 decoder 可能依赖 posterior 提供的信息完成重建，但 rollout 时只有 prior，模型就会出现明显的 train–inference gap。KL loss 不是一个可有可无的附加正则，而是把状态推断和未来预测连接起来的关键目标。

实际的 Dreamer 实现还可能使用 KL balancing、free bits / free nats、stop-gradient 等技巧，分别控制 prior 与 posterior 的学习速度，并避免 posterior collapse。不过这些是稳定训练的改进，不改变核心定义。

## 四、RSSM 的完整训练路径

对一段真实轨迹，训练过程可以概括为：

```text
observation o_t ──> encoder ──> e_t ─────────────┐
                                                  v
(h_{t-1}, z_{t-1}, a_{t-1}) ──> GRU ──> h_t ──> posterior q(z_t|h_t,e_t)
                                             └──> prior     p(z_t|h_t)
                                                        │
                                              sample z_t from posterior
                                                        │
                                                state (h_t, z_t)
                                                  /      |      \
                                         observation   reward   continue
                                           decoder      head      head
```

一个常见的 world model loss 是：

$$
\mathcal{L}_{\mathrm{model}}
= \mathcal{L}_{\mathrm{obs}}
+ \mathcal{L}_{\mathrm{reward}}
+ \mathcal{L}_{\mathrm{continue}}
+ \beta\mathcal{L}_{\mathrm{KL}}
$$

其中 observation reconstruction 让 latent 保留环境信息，reward / continue prediction 让它保留决策相关信息，KL 则让 prior 能在没有未来观测时复现 posterior 学到的状态空间。

## 五、训练和 imagination 的关键区别

| 阶段 | 是否有当前真实观测 | $z_t$ 来自哪里 | 用途 |
|---|---:|---|---|
| 表示学习 / posterior rollout | 有 | $q(z_t\mid h_t,e_t)$ | 从真实轨迹推断 latent state |
| 动力学学习 | 有，但 prior 不读取 | 比较 $q$ 与 $p$ | 用 KL 训练 prior |
| Imagination rollout | 没有 | $p(z_t\mid h_t)$ | 在 latent space 中预测未来、训练 actor / critic 或做规划 |

这也解释了为什么仅用 GRU 的模型可以做确定性 rollout，却不能表达“同一段历史之后存在多个合理未来”。它每次只能输出一个 hidden state；RSSM 则输出一个分布，可以采样不同的 $z_t$，表示多模态或不可约的不确定性。

## 六、如何判断一份代码是不是真正实现了 RSSM

可以快速检查下面几项：

1. latent state 是否同时包含 deterministic $h_t$ 和 stochastic $z_t$？
2. 是否有只依赖历史的 prior，以及额外读取当前 observation embedding 的 posterior？
3. $z_t$ 是否真的从参数化分布采样（或使用 categorical straight-through estimator）？
4. loss 中是否存在 posterior 与 prior 之间的 KL divergence？
5. imagination 时是否停止读取 observation，并改从 prior 生成后续 stochastic states？

如果代码只有：

```python
h_t = gru(torch.cat([h_prev, action], dim=-1))
next_state = mlp(h_t)
```

那么它是一个合理的 deterministic recurrent dynamics baseline，但不应被描述为完整的 variational RSSM。更准确的评价是：

> 当前实现只有 deterministic GRU，没有 stochastic state、posterior / prior distribution 和 KL loss。它可以作为简化版本或消融基线，但不是 PlaNet / Dreamer 意义上的完整 RSSM。

## 参考资料

- Hafner et al., [Learning Latent Dynamics for Planning from Pixels (PlaNet)](https://arxiv.org/abs/1811.04551)
- Hafner et al., [Dream to Control: Learning Behaviors by Latent Imagination (Dreamer)](https://arxiv.org/abs/1912.01603)
- Hafner et al., [Mastering Atari with Discrete World Models (DreamerV2)](https://arxiv.org/abs/2010.02193)
- Hafner et al., [Mastering Diverse Domains through World Models (DreamerV3)](https://arxiv.org/abs/2301.04104)
