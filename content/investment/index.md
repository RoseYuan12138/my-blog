---
title: "个人财务投资"
date: 2026-04-19
tags:
  - 投资策略
  - 资产配置
  - 税务优化
lang: zh
---

# 个人财务投资

一个小散户的定量投资之旅：从 16 年的真实回测数据出发，探索资产配置、策略择时、税务优化的边界。

## 核心文章

### 📚 从基础开始

- **[[asset-location-principles|资产配置与账户位置优化]]** — 为什么同一个 portfolio 放在不同账户（Roth vs Taxable vs Traditional）会多赚 $800k？Asset Location 的五条核心规则。

### 📊 策略回测与对比

- **[[dca-vs-lump-16year-backtest|定期定投 vs 一次性建仓：16 年回测对比]]** — 4 种策略 × 2 种场景，实测数据告诉你 FTD+Golden Cross 为什么是最优的。

### 💰 税后真实场景

- **[[tax-adjusted-optimal-strategy|税后真实场景：Roth+Taxable 账户分工最优解]]** — 把税考虑进去，FTD DCA 的优势被税吃掉 73%。但混合策略（Roth FTD + Taxable Pure DCA）能在 16 年变成 $2.35M。

### ⚠️ 风险与压力测试

- **[[stress-test-2008-crisis|压力测试：2008 金融危机下的策略表现]]** — 2010-2026 的回测缺少真熊市。用 2007-2012 的数据验证，FTD+Golden 是唯一在极端情景下活下来的策略。

## 快速导航

### 如果你只有 5 分钟
1. 读 [[tax-adjusted-optimal-strategy]] 的"结果"和"给 Rose 的操作建议"
2. 记住：**Roth 跑激进策略，Taxable 跑保守策略，分工比什么都重要**

### 如果你有 30 分钟
1. [[asset-location-principles]] — 理解为什么 asset location 那么重要
2. [[tax-adjusted-optimal-strategy]] — 了解 16 年的最优解是什么
3. [[dca-vs-lump-16year-backtest]] 的"策略对比汇总"表

### 如果你想深入研究
全部读一遍，按推荐顺序：
1. 税后真实场景（最实用）
2. 资产配置原理（理论基础）
3. 回测对比（策略详解）
4. 压力测试（风险管理）

## 核心结论一页纸

```
Asset Allocation = 买多少比例的股/债
Asset Location   = 这些资产分别放在哪个账户（Roth vs Taxable）

核心原则：
  - 预期回报高 + 税务效率低 → Roth
  - 预期回报中 + 税务效率高 → Taxable  
  - 预期回报低（Bond）     → Traditional 401k

最优策略（16年, $24k/年投入）：
  Roth IRA ($7k/年)     → FTD DCA + Golden Cross → $1.05M
  Taxable ($17k/年)     → Pure DCA on QQQ       → $1.29M
  ───────────────────────────────────────────────────
  合计（混合策略）      → ~$2.35M

同一策略，不同账户，利润差异可达 -50% 到 +50%
```

## 研究背景

这些文章基于 2026 年 4 月的系统回测研究，覆盖 16 年历史数据（2010-2026）+ 2008 危机压力测试。用的工具和数据源包括：

- **回测框架**: Python backtest on QQQ historical data (FMP API, yfinance, FRED)
- **策略信号**: FTD (O'Neil Follow-Through Day) + Golden Cross (50/200 SMA)
- **动态估值**: Forward PE 基于 AAPL/MSFT/GOOGL/COST TTM EPS × 增速
- **税务建模**: FIFO lot tracking，区分短期(50%) vs 长期(34%) 资本利得税
- **样本期间**: 2010-02 ~ 2026-03（正常市场）+ 2007-2012（2008 危机）

所有结论仅基于历史数据，不构成投资建议。

---

*最后更新：2026-04-19*
