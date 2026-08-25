---
title: 从 GNN、GCN、GAT 到 Graph Transformer：图上的信息如何传播？
date: 2026-08-25
tags:
  - machine-learning
  - graph-neural-network
  - transformer
---

# 从 GNN、GCN、GAT 到 Graph Transformer：图上的信息如何传播？

GNN、GCN、GAT 和 Graph Transformer 的名字很像，论文中的实现也五花八门。理解它们最有效的方法，不是背缩写，而是始终追问三个问题：

1. 更新节点 (i) 时，它可以读取哪些节点？
2. 不同来源的信息如何被加权和聚合？
3. 图结构是硬通信边界，还是只作为一种提示？

这三个问题决定了模型的信息传播范围、计算成本，以及它处理长距离依赖的能力。

## 1. 从图上的学习任务开始

一张带属性的图可以写成：

$$
G=(V,E,X),
$$

其中 (V) 是节点集合，(E) 是边集合，(X\in\mathbb R^{|V|\times d}) 是节点特征。边也可以带有方向、类型或连续特征。

常见任务有：

- **节点任务**：预测一篇论文的研究领域、一个账号是否异常；
- **边任务**：预测两个人是否会建立关系、两种药物是否相互作用；
- **图任务**：预测整个分子的性质、判断一段程序图是否存在漏洞。

和文本不同，图通常没有天然的第一个和第二个节点。理想情况下，任意重排节点编号，都不应该改变节点任务的等变性或图任务的最终结果。因此，图模型需要同时利用节点内容和连接结构，又不能把任意编号误认为真实顺序。

## 2. Message Passing：大多数 GNN 的共同骨架

现代 GNN 通常可以放进 Message Passing Neural Network 的框架。第 (l) 层包含三步：

### 生成消息

$$
m_{j\rightarrow i}^{(l)}
=
\operatorname{Message}^{(l)}
\left(h_i^{(l)},h_j^{(l)},e_{ji}\right).
$$

### 聚合邻居消息

$$
m_i^{(l)}
=
\operatorname{Aggregate}
\left(\left\{m_{j\rightarrow i}^{(l)}:j\in\mathcal N(i)\right\}\right).
$$

### 更新节点状态

$$
h_i^{(l+1)}
=
\operatorname{Update}^{(l)}\left(h_i^{(l)},m_i^{(l)}\right).
$$

`Aggregate` 通常采用 sum、mean、max 或 attention。这些操作不依赖邻居的排列顺序，因此适合图数据。

### 一层为什么只传播一跳？

考虑：

```text
S —— A —— B —— Q
```

一层更新中，节点只能读取当前邻居：

```text
第 1 层：S 的信息到 A
第 2 层：S 的信息经 A 到 B
第 3 层：S 的信息经 A、B 到 Q
```

因此，(L) 层局部消息传递模型中，节点表示最多直接依赖其 (L)-hop 邻域。这就是 GNN 的感受野。

普通 GNN 的下一次 forward 会重新从 (X) 开始，并不会自动接着上一次的隐藏状态继续传播。只有显式的循环消息传递、持续写回状态的动态图系统，或者多轮迭代算法，才会让有效传播范围继续增长。

## 3. GCN：对归一化邻居做加权平均

[GCN](https://arxiv.org/abs/1609.02907) 的经典形式为：

$$
H^{(l+1)}
=
\sigma\left(
\tilde D^{-1/2}\tilde A\tilde D^{-1/2}
H^{(l)}W^{(l)}
\right),
$$

其中：

$$
\tilde A=A+I,
$$

表示给每个节点添加自环；

$$
\tilde D_{ii}=\sum_j\tilde A_{ij}
$$

是对应的度矩阵。

从单个节点看，它相当于：

$$
h_i^{(l+1)}
=
\sigma\left(
\sum_{j\in\mathcal N(i)\cup\{i\}}
\frac{1}{\sqrt{\tilde d_i\tilde d_j}}
h_j^{(l)}W^{(l)}
\right).
$$

GCN 的核心直觉是：连接节点往往共享某些信息，因此可以反复进行“特征变换 + 邻域平滑”。

### GCN 的优点

- 结构简单；
- 稀疏实现下，单层成本大致为 (O(|E|d))；
- 对同质图上的节点分类通常很有效；
- 很适合作为图学习的基础模型和 baseline。

### GCN 的限制

第一，不同邻居的权重主要由度数决定，无法根据当前任务动态判断谁更重要。

第二，层数很深时可能出现 **over-smoothing**：相邻节点不断混合，表示逐渐变得相似。

第三，远处大量信息需要压缩进固定维度的中间节点，可能出现 **over-squashing**。

此外，图结构变化会改变度数和归一化系数。因此，新增一条边不仅带来新的消息，还可能改变原有消息的权重。

## 4. GAT：在邻居内部学习注意力权重

[GAT](https://arxiv.org/abs/1710.10903) 解决的是一个直接问题：既然邻居的重要性可能不同，为什么全部使用预先确定的归一化权重？

经典 GAT 首先计算邻居之间的未归一化分数：

$$
e_{ij}
=
\operatorname{LeakyReLU}
\left(a^\top[Wh_i\Vert Wh_j]\right),
$$

然后只在 (i) 的邻居集合中做 softmax：

$$
\alpha_{ij}
=
\frac{\exp(e_{ij})}
{\sum_{k\in\mathcal N(i)}\exp(e_{ik})}.
$$

最终更新为：

$$
h_i'
=
\sigma\left(
\sum_{j\in\mathcal N(i)}\alpha_{ij}Wh_j
\right).
$$

### GAT 和 GCN 到底差在哪？

```text
GCN：邻居权重主要由图的度数归一化决定
GAT：邻居权重由节点特征和训练目标动态学习
```

但二者通常有同一个硬约束：**只能读取邻居**。

$$
\alpha_{ij}=0,\qquad j\notin\mathcal N(i).
$$

所以，经典 GAT 仍然是一层走一跳。它不是因为使用了 attention，就自动拥有全局感受野。

### Multi-head attention

GAT 通常使用多个 head：

$$
h_i'
=
\mathbin\Vert_{k=1}^K
\sigma\left(
\sum_{j\in\mathcal N(i)}
\alpha_{ij}^{(k)}W^{(k)}h_j
\right).
$$

不同 head 可以学习不同的邻居关系。例如一个 head 更关注主题相似性，另一个更关注结构中心节点。最后一层也可以对多个 head 取平均，而不是拼接。

### Attention weight 是解释吗？

不能简单等同。较大的 (alpha_{ij}) 只表示该层给某个 value 较大的系数，最终影响还取决于：

- (W_Vh_j) 携带了什么；
- 多层之间如何组合；
- residual、normalization 和 MLP；
- 其他路径是否强化或抵消它。

因此 attention weight 可以帮助观察模型，但不能自动当作严格的因果解释。

## 5. Graph Transformer：把节点当作 token

Graph Transformer 通常对节点表示计算 query、key 和 value：

$$
q_i=W_Qh_i,\qquad
k_j=W_Kh_j,\qquad
v_j=W_Vh_j,
$$

$$
s_{ij}
=
\frac{q_i^\top k_j}{\sqrt{d_k}}+b_{ij},
$$

$$
h_i'
=
\sum_j\operatorname{softmax}_j(s_{ij})v_j.
$$

这里真正困难的不是 attention 本身，而是：文本有顺序，图却没有天然顺序。模型必须额外知道图结构。

### 图结构如何进入 Transformer？

常见方法包括：

- **邻接编码**：告诉模型 (i,j) 是否直接相连；
- **最短路径距离**：为不同图距离学习 bias；
- **边特征或边类型**：将关系语义加入 attention；
- **度数编码**：告诉模型节点的入度和出度；
- **Laplacian positional encoding**：使用图拉普拉斯特征向量描述全局位置；
- **random-walk encoding**：用随机游走统计量表达结构角色。

[Graphormer](https://arxiv.org/abs/2106.05234) 就是在标准 Transformer 上加入 centrality、最短路径和边特征等结构编码，让全局 self-attention 能够理解图。

## 6. 局部和全局 Graph Transformer 是两类不同模型

“Graph Transformer”并没有统一地规定每个节点能看谁。必须检查 attention mask。

### 局部 Graph Transformer

如果节点 (i) 只能关注邻居：

$$
s_{ij}=-\infty,qquad j\notin\mathcal N(i),
$$

它在传播范围上与 GAT 类似。如果每层允许关注 (r)-hop 邻域，那么 (L) 层最多覆盖 (Lr) 跳。

### 全局 Graph Transformer

如果任意两个节点都能计算 attention，那么：

```text
原图：S —— A —— B —— Q
模型内部：S ─────────→ Q
```

即使 (S,Q) 没有直接图边，(Q) 仍然可以读取 (S)。此时图边或图距离通常只改变 attention bias，也就是影响“关注多少”，而不是决定“能不能关注”。

这使模型更容易捕获长距离依赖，但标准全局 attention 的时间和显存成本通常是：

$$
O(|V|^2).
$$

当图包含数万甚至数百万节点时，直接对全图做 dense attention 往往不可行。

### 混合架构

实际系统经常同时使用：

```text
局部 Message Passing + 全局 Attention + 结构/位置编码
```

[GraphGPS](https://arxiv.org/abs/2205.12454) 是这一思路的代表：局部分支沿真实图边建模细粒度邻域，全局分支处理长距离依赖，再将两部分融合。全局分支还可以使用近似或线性 attention 来降低成本。

## 7. Interaction topology：模型内部到底谁能和谁通信

可以把每一层允许的信息流写成一个二值 support matrix：

$$
A_{ij}^{(l)}=
\begin{cases}
1,&\text{第 }l\text{ 层允许 }i\text{ 读取 }j,\\
0,&\text{否则。}
\end{cases}
$$

这就是该层的 interaction topology。

- GCN/GAT：support 通常来自邻接矩阵加自环；
- 局部 Graph Transformer：support 来自局部 attention mask；
- 全局 Graph Transformer：support 通常是全连接的；
- 混合模型：局部分支和全局分支共同形成计算路径。

多层模型的最终依赖由这些 support 逐层组合。如果直接连接被 mask 掉，仍然可能存在间接路径：

```text
第 1 层：S → A
第 2 层：A → Q
```

因此，判断两个节点是否能互相影响，不能只看某一层有没有直接 attention，还要检查整个多层计算图中是否存在路径。

## 8. Mask 阻断的是计算路径

attention mask 通常把不允许的 logit 设置为负无穷：

$$
M_{ij}=-\infty
\quad\Longrightarrow\quad
\alpha_{ij}=0.
$$

于是对应的直接依赖消失：

$$
\frac{\partial h_i^{(l+1)}}
{\partial h_j^{(l)}}=0.
$$

如果从源节点到目标节点的所有多层路径都被切断，那么源节点不可能通过这些计算路径改变目标输出。

但反过来，“存在路径”只表示**可能影响**，并不表示一定产生明显效果：

```text
没有路径 → 结构上不可能影响
存在路径 → 可能影响
实际影响多大 → 取决于参数、输入和所有路径的组合
```

这一区分对模型分析很重要。全局 attention 意味着全局可达，但不意味着模型会同等重视所有节点。

## 9. 为什么不直接堆很多层 GNN？

如果长距离信息需要很多层才能到达，最直接的想法是继续加深模型。但深层 GNN 会遇到几个典型困难。

### Over-smoothing

反复平均邻域信息后，不同节点的表示越来越相似，模型难以区分节点。

### Over-squashing

随着 hop 数增加，远处节点数量可能指数增长，但所有信息都必须通过少数中间节点，被压缩进固定维度向量。

### 优化困难和噪声传播

更多层意味着更长的梯度路径，也会把更远处的无关信息引入目标节点。

全局 attention 提供了更短的长距离通信路径，但代价是二次复杂度、更弱的局部归纳偏置，以及更大的潜在信息交互范围。这也是很多现代架构选择“局部消息传递 + 稀疏或近似全局 attention”的原因。

## 10. 一张表看懂区别

| 模型 | 一层读取范围 | 权重如何产生 | 图边的角色 | 典型单层成本 |
|---|---|---|---|---|
| GCN | 一跳邻居 | 度数归一化 | 硬通信边界 | (O(|E|d)) |
| GAT | 一跳邻居 | 邻居内 learned attention | 硬通信边界 | 约 (O(|E|d)) |
| 局部 Graph Transformer | mask 指定的邻域 | dot-product attention + 结构编码 | 通常是硬边界 | 取决于 mask 稀疏度 |
| 全局 Graph Transformer | 全部节点 | dot-product attention + 结构编码 | bias/特征，不一定是边界 | (O(|V|^2d)) |
| 混合 Graph Transformer | 局部边 + 全局通道 | 局部聚合与全局 attention 融合 | 同时提供归纳偏置和结构编码 | 依全局模块而定 |

## 11. 实际选型

### 选择 GCN，当：

- 需要一个简单、稳定的 baseline；
- 图较大且稀疏；
- 邻接关系本身具有较强可信度；
- 任务主要依赖局部同质性。

### 选择 GAT，当：

- 不同邻居的重要程度差异明显；
- 希望在局部邻域中动态选择信息；
- 仍然需要保持稀疏局部计算。

### 选择全局 Graph Transformer，当：

- 长距离依赖非常重要；
- 图规模允许 dense attention，或已有有效近似；
- 能提供合适的结构和位置编码；
- 不希望信息必须经过许多中间节点才能到达。

### 选择混合架构，当：

- 既需要真实图边提供的局部归纳偏置，又需要全局上下文；
- 图较大，无法直接使用完整的 (O(|V|^2)) attention；
- 任务同时包含局部化学结构、局部关系和远距离依赖。

## 12. 最值得记住的结论

```text
GCN：固定规则聚合邻居
GAT：动态选择邻居，但通常仍只看邻居
局部 Graph Transformer：用 Transformer 机制处理受 mask 限制的节点
全局 Graph Transformer：所有节点可以直接交互，图结构更多作为编码或 bias
```

因此，以后看到一个新的“Graph Transformer”，不要仅凭名称判断它是局部还是全局。应该直接查看：

1. attention 是在邻居中计算，还是在全部节点中计算？
2. 图边是 attention mask，还是 attention bias？
3. 使用了哪些结构或位置编码？
4. 是否同时保留了局部 message-passing 分支？
5. 全局 attention 的复杂度如何控制？

回答完这些问题，模型的基本原理、传播范围和主要取舍就已经清楚了。

## 参考资料

- Kipf & Welling, [Semi-Supervised Classification with Graph Convolutional Networks](https://arxiv.org/abs/1609.02907), ICLR 2017.
- Veličković et al., [Graph Attention Networks](https://arxiv.org/abs/1710.10903), ICLR 2018.
- Ying et al., [Do Transformers Really Perform Bad for Graph Representation?](https://arxiv.org/abs/2106.05234), NeurIPS 2021.
- Rampášek et al., [Recipe for a General, Powerful, Scalable Graph Transformer](https://arxiv.org/abs/2205.12454), NeurIPS 2022.
