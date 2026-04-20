---
title: "税后真实场景：Roth+Taxable 账户分工最优解"
date: 2026-04-19
tags:
  - 税后分析
  - 账户分工
  - Roth IRA
  - 实际应用
lang: zh
english: investment/tax-adjusted-optimal-strategy.en.md
---

## 这篇在讲什么

前两篇分析都是 pre-tax 口径——策略回报好看，但没扣税。问题是：**Rose 的边际税率是 50.3%**，短期资本利得直接砍一半。

这篇把税后机制加进来（FIFO lot tracking，按持仓时间区分短期/长期税率），用 Rose 的真实税率和账户结构跑回测，回答一个核心问题：

> **Roth 和 Taxable 各该跑什么策略？**

结论先放这儿：**★ 混合策略（Roth 跑 FTD DCA + Taxable 跑 Pure DCA）16 年终值约 $2.35M，比任何单一策略多赚 $470k ~ $680k。**

---

## Rose 的真实税务情况

| 项目 | 数值 |
|---|---|
| TC | ~$377k（$260k base + $117k RSU vest） |
| 身份 | CA H1B 后 RA，单身 |
| **边际税率** | **★ ~50.3%**（37% Fed + 13.3% CA + SDI） |
| 短期 CG（持仓 <1 年） | **50%** |
| 长期 CG（持仓 ≥1 年） | **34%**（20% Fed + 10.3% CA + 3.8% NIIT） |

### 账户瀑布

```
401k match（公司出）
  → HSA $4.4k/年
    → Backdoor Roth $7k/年
      → Taxable Robinhood 剩余 $17k/年
```

**年度可投资 DCA 资金 = $24k = $7k Roth + $17k Taxable**

---

## 税后三策略对比

回测区间：2010-02-11 ~ 2026-03-31（~16.1 年），每年投入 $24k。

| 策略 | 税后终值 | Roth 部分 | Taxable 部分 | IRR | MaxDD | 交易次数 |
|---|---|---|---|---|---|---|
| **Pure DCA（纯 QQQ）** | $1,875,835 | $585,560 | $1,290,275 | **10.28%** | -34.2% | 0 |
| FTD DCA（+Golden Cross） | $1,662,579 | **$1,054,387** | $608,191 | 9.45% | -43.7% | 48 |
| **C2 Dyn PE** | **$1,879,594** | $582,228 | **$1,297,367** | **10.29%** | -34.4% | 13 |

**★ 税后 Pure DCA 和 C2 基本打平，FTD DCA 掉到最后。**

这跟 pre-tax 的结论完全不同。为什么？

### 税吃掉了多少？

| 策略 | Pre-tax | Post-tax | 被税吃掉 |
|---|---|---|---|
| FTD DCA | $3,186,670 | $1,662,579 | **★ -$1,524,091（-48%！）** |
| C2 Dyn PE | $2,019,775 | $1,879,594 | -$140,181（-7%） |
| Pure DCA | $1,823,387 | $1,875,835 | ~持平 |

**FTD DCA 的 $1.37M pre-tax alpha 几乎完全被税负吞没。** 48 次换仓 × 平均持仓 <1 年 × 50% 短期税 = 每次砍一半再复利，差距越滚越大。

Pure DCA 全程 0 次卖出 → $0 interim tax → 复利最纯粹。

---

## 关键发现

### 1. 同一策略，账户不同，结果天差地别

把 FTD DCA 按账户拆开看：

| 账户 | Pure DCA | FTD DCA | C2 | 赢家 |
|---|---|---|---|---|
| **Roth**（免税，$7k/年） | $585,560 | **★ $1,054,387** 🏆 | $582,228 | FTD +$470k |
| **Taxable**（吃税，$17k/年） | $1,290,275 | $608,191 | **$1,297,367** 🏆 | Pure/C2 平手 |

**★ FTD DCA 在 Roth 里胜 Pure DCA $469k（+80%），在 Taxable 里输 Pure DCA $682k（-53%）。**

同一个策略，放错账户直接亏 $680k。这就是 asset location 的力量。

### 2. 混合策略碾压单一策略

既然 Roth 和 Taxable 是完全独立的账户，可以分别选最优策略：

| 方案 | 16 年终值 | vs 全 Pure DCA |
|---|---|---|
| **★ Mixed: Roth FTD + Taxable Pure/C2** | **~$2.35M** | **+$470k** |
| 全 Pure DCA | $1.88M | 基准 |
| 全 C2 | $1.88M | +$0 |
| 全 FTD DCA | $1.66M | **-$210k** |

**★ 混合策略比任何单一策略多赚 $470k ~ $680k。** 这是零成本的优化——不需要更多资金，不需要更多风险，只是把策略放对账户。

### 3. 高换手 + 高税率 = 复利杀手

FTD DCA 在 Taxable 里的拆解：

- Pre-tax Taxable 部分估计值：~$2.27M
- Post-tax Taxable 部分：$608k
- **★ 税负吃掉了 73%**

核心机制：每次换仓 → realize 全部未实现收益 → 持仓通常 <1 年 → 50% 短期税 → **砍半后才能继续复利**。这个过程重复 48 次，雪球被反复削小。

### 4. 回撤也受税影响

| 策略 | Pre-tax MaxDD | Post-tax MaxDD |
|---|---|---|
| Pure DCA | -34.2% | -34.2%（一致） |
| FTD DCA | -39.5% | -43.7%（税放大了下跌） |
| C2 | -45.3% | -34.4%（高点交税 = 被迫锁利） |

税不只吃收益，还改变了回撤形状。FTD 因为税把本金削小，跌起来更痛。C2 反而因为高点 trim 时交了税，相当于被迫锁利，回撤反而变小。

---

## 给 Rose 的具体操作建议

### Roth IRA（$7k/年）→ FTD DCA + Golden Cross

```
每月自动投入 $583
信号 active (Dual Golden Cross): 全仓 TQQQ
信号失效: 全仓 QQQ
```

为什么可以大胆：**Roth 永不交税**，换手率不影响回报。FTD 的 48 次交易在这里完全无成本。这个账户就是为高换手策略而生的。

### Taxable Robinhood（$17k/年）→ Pure DCA

```
每两周 $700 入 QQQ（总 $17k/年）
不卖，不做任何 timing
```

为什么选最简单的：Pure DCA 和 C2 终值只差 $7k（$1.29M vs $1.30M），完全不值得为这点差距增加操作复杂度。纯买入持有，终端全部按 long-term capital gains 34% 税率计税，这是 Taxable 账户的最优路径。

### 两个账户的分工逻辑

| | Roth | Taxable |
|---|---|---|
| **策略** | FTD DCA + Golden Cross | Pure DCA |
| **标的** | QQQ ↔ TQQQ（按信号切换） | 只买 QQQ |
| **换手率** | 高（~48 次/16 年） | 零 |
| **税负** | 完全免税 | 仅终端长期 CG |
| **操作频率** | 关注 Golden Cross 信号 | 设好自动投入，忘掉 |

---

## 当前仓位的处理

你现在的 **QQQ 30 股 + TQQQ 200 股** 是一笔性（lump sum）投入，不属于 DCA 范畴。

建议：
- 按 **LUMP 场景最优策略 = FTD + Golden Cross** 管理（详见系列第二篇）
- 当前信号状态：**FTD + Golden Cross 都 active**（4/08 Dual 确认 + 牛市结构），持仓方向正确
- 未来新增 DCA 资金按上面的账户分工进入，跟现有仓位分开管理

---

## 简化版建议

如果觉得上面太复杂，三句话版本：

1. **Roth 里按 FTD 信号操作**（Golden Cross active 时买 TQQQ，失效时换 QQQ）
2. **Taxable 里每两周 $700 买 QQQ，不卖**
3. 现有持仓继续持有，跟着 FTD 信号走

就这样。数据说 C2 在 Taxable 里多赚 $7k，但操作复杂度高得多，性价比不值。**简单策略 + 正确的账户分工 > 复杂策略放错地方。**

---

## 局限性和注意事项

### 终端税未计入

Pure DCA 的 Taxable 账户末端有大量未实现收益（~$1M+）。如果 2026 年一次性全清，需要交 34% 长期税（~$340k）。但实盘不会一次全清——这笔税是延迟的、可分批缴的，不等于现实成本。

### 回测区间偏牛

2010–2026 是牛市主导期，FTD 的"永远在场"哲学天然占便宜。没遇到 2008 级别的全面熊市。

### RSU Vest 的额外资金

2026-07 的 $117k RSU vest 后 sell-to-cover 会带来 ~$60k 的额外 taxable 流入。这笔钱按什么策略分配没有建模——实际现金流会比假设的"每月稳定投入"更 lumpy。

### Backdoor Roth 的前提条件

Backdoor Roth 依赖 Traditional IRA 保持 $0 余额。如果跳槽后 rollover pre-tax 401k → Traditional IRA，会污染 pro-rata rule，Backdoor 通道失效。**每次工作变动前务必确认。**

### 税率可能变化

当前用的是 2025/2026 税法估算。如果未来立法调高 capital gains 税率（比如长期 CG 升到 ~40%），Pure DCA 的"延迟缴税"优势会更突出，FTD 在 Taxable 的劣势更大。

### 其他税优空间

401k 和 HSA 未纳入本分析。401k 一般只能投 mutual fund，不适合 QQQ/TQQQ 频繁切换。HSA 如果走投资模式（Fidelity HSA），可以跑 Pure DCA QQQ。

### NIIT 门槛

3.8% NIIT 只对 MAGI > $200k 单身适用。Rose 目前已超，但未来若收入骤降（回校、gap year），长期 CG 税会从 34% 降到 30.3%，对 Pure DCA 终端税有利。

---

## 系列导航

这是"投资策略量化分析"系列的第三篇，也是最贴近实操的一篇：

1. [DCA 策略量化对比](/investment/dca-strategy-comparison) — pre-tax DCA 四策略对比
2. [四策略全景回测](/investment/four-strategy-full-comparison) — LUMP + DCA 双场景 pre-tax
3. **本篇：税后真实场景** — 加入税后机制，得出账户分工最优解 ← 你在这里

**核心结论：不是选哪个策略的问题，是把策略放对账户的问题。**
