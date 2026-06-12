# Harness Engineering Framework

> 你只需要说出你想要什么，剩下的交给系统。

[English version](README_EN.md)

## 这是什么？

想象一下：你有一个想法，但不知道怎么实现。你告诉这个系统"我需要一个客户入驻系统"，它会：

1. **理解你的想法** — 把模糊的需求翻译成清晰的任务定义
2. **设计工作方式** — 自动生成规则、流程、检查点
3. **分配专业角色** — 自动创建一组 AI 代理，各司其职
4. **编排执行** — 规划谁先做、谁后做、谁并行做
5. **验证结果** — 自动检查产出是否达标
6. **越用越聪明** — 每次犯错都会让系统变得更好
7. **自我进化** — 系统会主动优化自己的规则、流程和代理配置，进化规则本身也会进化

**一句话**：这是一个"会进化的 AI 代理管理系统"——它确保 AI 代理干活靠谱，而且会越来越靠谱。

---

## 自动化交易系统

本项目已生成了一个完整的**自动化交易系统**，面向散户投资者，覆盖投研、策略、回测、执行全流程。

### 快速开始

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 初始化项目目录
trading init

# 3. 查看所有命令
trading --help
```

### 系统架构

```
src/trading_system/
├── core/          事件总线、配置管理、审计日志
├── data/          市场数据获取(日线/日内)、缓存、观察列表
├── pipeline/      🔥 全市场扫描→评分→策略融合→交易完整管线
├── strategy/      策略基类 + 3个内置策略 + 协整配对 + PCA套利
├── portfolio/     协方差估计、组合优化、风险平价/HRP、因子模型
├── ml/            HMM状态识别、卡尔曼滤波、波动率预测、微观结构信号
├── risk/          仓位计算、止损、最大回撤、熔断机制
├── backtest/      回测引擎 + Monte Carlo概率回测 + 显著性检验
├── execution/     纸上交易Broker + 冲击成本模型 + 执行调度 + TCA
├── analysis/      市场状态检测(牛/熊/震荡)、技术指标
├── sentiment/     市场情绪分析、热点捕捉、持续性分析
├── research/      投研数据源(新闻/研报/公告)、投研引擎
└── cli/           Click命令行 + Rich终端界面
```

### 命令一览

| 命令组 | 命令 | 说明 | 所属阶段 |
|--------|------|------|----------|
| `trading init` | — | 初始化项目目录和配置 | — |
| `trading data` | `fetch` | 获取股票日线数据 | — |
| `trading data` | `analyze` | 分析技术指标和市场状态 | — |
| `trading data` | `intraday` | 获取日内多频率K线数据 | Phase 4 |
| `trading watchlist` | `create` | 创建观察列表 | — |
| `trading watchlist` | `add` | 添加股票到观察列表 | — |
| `trading watchlist` | `list` | 列出所有观察列表 | — |
| `trading strategy` | `list` | 列出可用策略 | — |
| `trading strategy` | `backtest` | 回测指定策略 | — |
| `trading sentiment` | `analyze` | 分析市场情绪 | — |
| `trading sentiment` | `hotspot` | 捕捉市场热点 | — |
| `trading sentiment` | `persistence` | 分析热点持续性 | — |
| `trading research` | `symbol` | 个股投研分析 | — |
| `trading research` | `market` | 全市场投研概览 | — |
| `trading trade` | `status` | 查看交易系统状态 | — |
| `trading trade` | `start` | 启动交易引擎 | — |
| `trading trade` | `recommend` | 全市场扫描 + 多因子评分 + 推荐报告 | — |
| `trading trade` | `daily-run` | 每日完整流程: 扫描→评分→策略融合→报告 | — |
| `trading trade` | `daily-trade` | 每日自动交易: 扫描→评分→融合→风控→下单 | — |
| `trading trade` | `estimate-impact` | 估算市场冲击成本 | Phase 1 |
| `trading trade` | `execution-plan` | 生成最优执行计划(TWAP/VWAP/IS) | Phase 1 |
| `trading trade` | `tca-report` | 交易成本分析周度报告 | Phase 1 |
| `trading trade` | `tca-order` | 单笔订单TCA明细查询 | Phase 1 |
| `trading trade` | `covariance` | 计算协方差与相关性矩阵 | Phase 2 |
| `trading trade` | `optimize-portfolio` | 组合优化(Markowitz/RiskParity/HRP) | Phase 2 |
| `trading trade` | `factor-exposure` | 因子暴露与Alpha归因分析 | Phase 2 |
| `trading trade` | `find-pairs` | 自动发现协整配对 | Phase 3 |
| `trading trade` | `hmm-state` | HMM市场状态识别 | Phase 3 |
| `trading trade` | `kalman-hedge` | 卡尔曼滤波动态对冲比率 | Phase 3 |
| `trading trade` | `vol-forecast` | 波动率预测(EWMA/GARCH) | Phase 4 |
| `trading trade` | `tick-analysis` | Tick数据买卖压力分析 | Phase 4 |
| `trading trade` | `test-significance` | Deflated Sharpe显著性检验 | Phase 5 |
| `trading trade` | `backtest-mc` | Monte Carlo概率回测 | Phase 5 |

---

### 📊 数据管理

```bash
# 获取股票日线数据（默认akshare A股数据源）
trading data fetch 600519

# 指定数据源和日期范围
trading data fetch 600519 --source akshare --start 20230101 --end 20240101

# 保存到CSV文件
trading data fetch 600519 --save

# 分析技术指标（RSI、MACD、布林带、ATR、ADX等）
trading data analyze 600519
```

### 📋 观察列表

```bash
# 创建观察列表
trading watchlist create 自选股

# 添加股票
trading watchlist add 自选股 600519 -n 贵州茅台
trading watchlist add 自选股 000858 -n 五粮液

# 查看所有列表
trading watchlist list
```

### 🎯 策略与回测

系统内置3个策略：

| 策略 | 类型 | 适合市场 | 说明 |
|------|------|----------|------|
| `trend_following` | 趋势跟踪 | 牛市/熊市 | 双均线交叉，快线上穿慢线做多 |
| `mean_reversion` | 均值回归 | 震荡市 | 布林带+RSI，超卖买入超买卖出 |
| `breakout` | 通道突破 | 牛市/熊市 | 突破N日最高价做多 |

```bash
# 查看可用策略
trading strategy list

# 回测策略
trading strategy backtest trend_following 600519

# 指定初始资金和日期
trading strategy backtest trend_following 600519 --capital 200000 --start 20230101

# 传入自定义策略参数（JSON格式）
trading strategy backtest trend_following 600519 --params '{"fast_period": 10, "slow_period": 30}'
```

回测报告自动计算**7大关键量化指标**：

| 指标 | 说明 | 评估标准 |
|------|------|----------|
| 胜率 (Win Rate) | 盈利交易占比 | ≥50% 优秀 |
| 风险/回报比 (R/R) | 平均盈利/平均亏损 | ≥2.0 优秀 |
| 最大回撤 (Max DD) | 权益峰值到谷底最大跌幅 | ≤15% 安全 |
| 每笔风险% | 单笔风险占总资金比 | ≤2% 合理 |
| 年化收益率 | 复利年化回报 | ≥30% 优秀 |
| 最大连亏次数 | 连续亏损最大次数 | ≤5 可承受 |
| 平均R倍数 | 盈亏统一为R单位 | ≥1.5 大赚小赔 |

### 🌡️ 市场情绪分析

```bash
# 分析市场情绪（默认上证指数）
trading sentiment analyze

# 指定指数
trading sentiment analyze -s 399001

# 捕捉市场热点（行业板块+概念板块）
trading sentiment hotspot

# 显示更多热点
trading sentiment hotspot -t 20

# 分析热点持续性
trading sentiment persistence 半导体
```

情绪评分基于6个维度：
- 涨跌家数比（20%权重）
- 涨跌停比（20%权重）
- 换手率（15%权重）
- 新高新低比（15%权重）
- 融资融券变化（15%权重）
- 指数趋势（15%权重）

5级情绪等级：极度恐惧 😱 → 恐惧 😟 → 中性 😐 → 贪婪 😊 → 极度贪婪 🤑

热点动量6级标签：emerging → continuing → strengthening → climax → weakening → fading

### 🔍 投研分析

```bash
# 个股投研分析（新闻+研报+公告）
trading research symbol 600519

# 全市场投研概览（热点+轮动+资金流向）
trading research market
```

投研引擎自动：
- 获取并分析最新新闻，判断正面/负面情绪
- 汇总研报评级和目标价
- 检查重要公告和风险提示
- 生成关键发现和风险警告

### 💰 自动化交易（核心流程）

```bash
# 每日推荐报告（扫描→评分→推荐）
trading trade recommend --candidates 200 --top 20

# 每日完整分析（扫描→评分→策略融合→报告）
trading trade daily-run --candidates 200 --top 30

# 每日自动交易（扫描→评分→融合→风控→下单）
trading trade daily-trade --candidates 200 --top 30          # 模拟运行
trading trade daily-trade --candidates 200 --top 30 --live   # 实盘交易（需QMT）
```

**完整交易管线架构：**

```
全市场扫描        多因子评分         策略融合            风控+执行
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────────┐
│ 5500+只A股│──→│ 技术40%  │──→│ 趋势跟踪      │──→│ 风控校验      │
│ 过滤ST/退市│    │ 基本面30%│    │ 均值回归      │    │ 仓位计算      │
│ PE/PB筛选  │    │ 资金20%  │    │ 突破策略      │    │ T+1检查       │
│ 成交量排序  │    │ 情绪10%  │    │ 共识加权融合   │    │ 熔断保护      │
└──────────┘    └──────────┘    └──────────────┘    └──────────────┘
                                                        ↓
                                                  ┌──────────────┐
                                                  │ Paper/QMT下单 │
                                                  │ 交易报告 JSON │
                                                  │ 交易信号 JSON │
                                                  └──────────────┘
```

**输出文件** (`./output/`)：
| 文件 | 说明 |
|------|------|
| `daily_{date}.md` | Markdown 日报 |
| `trade_signals_{date}.json` | 结构化交易信号（含止损止盈、策略共识） |
| `daily_summary_{date}.json` | 每日统计汇总 |
| `trade_report_{date}.json` | 交易执行报告（订单明细） |

### 💰 交易执行

```bash
# 查看交易系统状态
trading trade status

# 启动纸上交易（默认）
trading trade start --mode paper
```

**安全机制**：
- 默认纸上交易模式，需显式 `--mode live` 才能实盘
- 每笔交易强制止损
- 每笔风险控制在总资金的2%
- 最大回撤超限自动触发熔断
- 日亏损超5%触发熔断，冷却3天
- 所有操作记录审计日志

---

## 🔬 Phase 1：执行 Alpha — 保护策略 Edge

> **核心理念**：好的策略被糟糕的执行毁掉。执行优化的ROI远高于策略优化。

### 市场冲击成本估算

基于 Almgren-Chriss 框架，估算大单交易的市场冲击：

```
总冲击 = 临时冲击 + 永久冲击
临时冲击 = η × σ × ν^β    (流动性消耗，执行后反弹)
永久冲击 = γ × σ × ν      (信息泄露，改变均衡价格)
```

```bash
# 估算买入50,000股贵州茅台的市场冲击
trading trade estimate-impact -s 600519 -q 50000

# 指定到达价格
trading trade estimate-impact -s 600519 -q 50000 -p 1800.00
```

输出包括：临时冲击(bps)、永久冲击(bps)、总冲击(bps)、预期成交价格。

### 最优执行计划

支持三种执行策略，将大单拆分为子单，最小化执行成本：

| 策略 | 原理 | 适用场景 |
|------|------|----------|
| `twap` | 等量拆分 | 简单场景，无市场判断 |
| `vwap` | 按历史成交量分布拆分 | 追求与市场VWAP对齐 |
| `implementation_shortfall` | 优化冲击-风险权衡 | 大单执行，需要控制风险 |

```bash
# VWAP执行：30分钟内10个子单执行50,000股
trading trade execution-plan -s 600519 -q 50000 -st vwap -m 30 -n 10

# TWAP等量执行
trading trade execution-plan -s 600519 -q 20000 -st twap -m 15 -n 5

# Implementation Shortfall最优执行（需先有冲击模型）
trading trade execution-plan -s 600519 -q 100000 -st implementation_shortfall -m 60 -n 12
```

### TCA 交易成本分析

监控每一笔订单的执行质量，周度汇总所有执行成本：

```bash
# 生成周度TCA报告
trading trade tca-report

# 查看单笔订单TCA明细
trading trade tca-order -o "ORDER-001-S0"
```

**TCA指标说明**：
- **IS (bps)**：Implementation Shortfall，总执行成本
- **延迟成本 (bps)**：从决策到第一笔成交期间的市场变动
- **冲击成本 (bps)**：最后一笔与第一笔成交之间的市场变动

---

## 📊 Phase 2：组合数学 — 风险预算与控制

> **核心理念**：单票策略用止损控制风险，多票组合用数学控制风险。协方差矩阵是所有组合优化的基石。

### 协方差矩阵估计

稳健的协方差估计是组合优化的前提。当股票数多、样本量少时，样本协方差不稳定且可能不可逆：

```bash
# Ledoit-Wolf收缩估计（推荐，自动处理样本不足问题）
trading trade covariance -s "600519,000858,000568,002304,000651"

# 指数加权协方差（近期数据权重更高）
trading trade covariance -s "600519,000858,000568" -m exponential

# 样本协方差（样本充足时可用）
trading trade covariance -s "600519,000858,000568" -m sample
```

输出包含相关性矩阵热力图（绿色 = 高相关，红色 = 负相关）。

### 组合优化

```bash
# Markowitz均值-方差优化（需要预期收益和协方差）
trading trade optimize-portfolio -s "600519,000858,000568,002304,000651" -m markowitz

# 风险平价（所有资产贡献相等风险，不依赖收益预测）
trading trade optimize-portfolio -s "600519,000858,000568" -m risk_parity

# HRP层次风险平价（利用聚类结构，对噪声更稳健）
trading trade optimize-portfolio -s "600519,000858,000568,002304,000651,002415" -m hrp
```

**三种方法对比**：

| 方法 | 输入 | 优点 | 缺点 |
|------|------|------|------|
| Markowitz | 预期收益 + 协方差 | 理论最优 | 对收益率预测极度敏感 |
| Risk Parity | 仅协方差 | 不依赖收益预测 | 可能低收益 |
| HRP | 仅协方差 | 利用层次结构，最稳健 | 计算稍复杂 |

输出包含：年化收益、年化波动、夏普比率、分散化比率、最优权重柱状图。

### 因子暴露分析

使用 PCA 自动提取 A 股统计因子，分解组合收益来源：

```bash
trading trade factor-exposure -s "600519,000858,000568,002304,000651"
```

输出：
- **因子贡献表**：每个因子的暴露度、因子收益、贡献收益
- **Alpha 占比**：不能被已知因子解释的"真 Alpha"占总收益的百分比
- Alpha 占比 < 30% → 策略收益主要是 Beta，需要审视策略独特性

---

## 📈 Phase 3：统计 Alpha 发现

> **核心理念**：真正的 Alpha 来自发现市场定价中的统计规律，而非主观判断。

### 协整配对交易

自动扫描多只股票，发现具有稳定协整关系的配对：

```bash
# 扫描默认股票池（10只大盘蓝筹）
trading trade find-pairs

# 自定义股票池
trading trade find-pairs -s "600519,000858,000568,002304,000651,002415,000001,600036,601318,300750"
```

**工作原理**：
1. 两两测试 Johansen 协整关系（p < 0.05）
2. OLS 估计对冲比率 β
3. ADF 检验价差平稳性（t-stat < -3.0）
4. 过滤低相关性配对（|ρ| < 0.7）
5. 每20个交易日自动 re-test，失效配对自动停用

配对策略信号规则：
- z-score > 2.0 → 做空 spread（卖 Y + 买 X）
- z-score < -2.0 → 做多 spread（买 Y + 卖 X）
- z-score 回归 0 附近 → 平仓

### 卡尔曼滤波动态对冲比率

传统 OLS 对冲比率是静态的，卡尔曼滤波提供随时间自适应更新的 β：

```bash
trading trade kalman-hedge -p 600519-000858
```

输出对比：OLS 静态 β vs 卡尔曼滤波最终 β ± 标准差。

**何时使用卡尔曼滤波**：
- 配对关系可能因基本面变化而漂移
- β 标准差 > 0.1 → 关系不够稳定
- 更新次数 > 100 → 滤波已充分收敛

### HMM 市场状态识别

隐马尔可夫模型自动识别当前市场处于何种状态（牛市/熊市/震荡）：

```bash
# 分析沪深300的市场状态
trading trade hmm-state -s 000300

# 分析上证指数
trading trade hmm-state -s 000001
```

模型自动训练并保存到 `./data/models/hmm/`，支持加载历史模型。输出状态概率分布和各状态的平均收益/波动特征。

### PCA 统计套利

用 PCA 提取共性因子，做多被低估的股票、做空被高估的股票：

> PCA 套利属于高级策略，需要运行完整的策略引擎，CLI 提供的是 PCA 因子分析入口。实际使用参考 `src/trading_system/strategy/pca_arbitrage.py`。

---

## ⚡ Phase 4：日内多频率 & 微观结构

> **核心理念**：日线数据丢失了日内微观结构信息。在更高频率上捕捉信号，可以获得额外的 Alpha。

### 日内 K 线数据

```bash
# 获取贵州茅台30分钟K线（最近5个交易日）
trading data intraday 600519 -p 30min -d 5

# 获取5分钟K线
trading data intraday 600519 -p 5min -d 3

# 获取60分钟K线
trading data intraday 600519 -p 60min -d 20
```

支持周期：`5min` / `15min` / `30min` / `60min`。

### 波动率预测

```bash
# EWMA波动率预测（RiskMetrics λ=0.94）
trading trade vol-forecast -s 600519 -m ewma

# GARCH(1,1)波动率预测
trading trade vol-forecast -s 600519 -m garch
```

输出当前日波动率 + 未来1~5天的预测波动率（均为年化值）。

**使用场景**：
- 动态调整止损宽度（高波动 → 宽止损）
- 仓位动态调整（高波动 → 减仓）
- 期权定价参考

### Tick 数据买卖压力

逐笔成交数据分析，判断当前市场的买方/卖方力量对比：

```bash
trading trade tick-analysis -s 600519
```

输出核心信号：
- **成交量不平衡**：(买量 - 卖量) / 总成交量，正值 = 买方主导
- **单笔大小不平衡**：大单是买方还是卖方更多
- **Tick方向**：Tick中涨跌比例，修正报价驱动的偏差
- **综合评分** (>0.2 = 买方强势, <-0.2 = 卖方强势)

---

## 🧪 Phase 5：回测严谨性 — 保护你不被自己骗

> **核心理念**：99% 的回测 Sharpe Ratio 是数据挖掘的产物。必须用统计方法区分"真实 Alpha"和"运气"。

### Deflated Sharpe Ratio 显著性检验

```bash
# 测试策略的统计显著性（50次假设参数尝试）
trading trade test-significance -s trend_following -y 000001 -n 50
```

**检验指标说明**：

| 指标 | 解释 | 优秀阈值 |
|------|------|----------|
| 原始 Sharpe | 常规年化夏普比率 | > 1.5 |
| **Deflated Sharpe** | 校正了多次尝试的数据挖掘偏差 | **> 2.0** |
| Haircut Sharpe | 简化版：夏普 × (1 - √(ln(N)/T)) | > 1.0 |
| 月度 Alpha t-stat | 月度超额收益的 t 检验 | > 2.0 |
| 显著性等级 | 综合判断 | SIGNIFICANT / HIGHLY SIGNIFICANT |

**为什么需要 Deflated Sharpe？**
- 如果你测试了50个参数组合，选出最好的那个，它的 Sharpe 是"被选出来的"
- Expected Maximum Sharpe under null ≈ √(2 × ln(N))
- 你看到的可能只是运气最好的那次，而非策略真的有 Alpha
- Deflated Sharpe 减去了这个"选择偏差"

### Monte Carlo 概率回测

传统回测给出"一个结果"，Monte Carlo 回测给出"结果分布"：

```bash
# 500条Monte Carlo路径的概率回测
trading trade backtest-mc -s 600519 -st trend_following -n 500
```

输出：
- **最终权益分布**：P10 / P25 / P50 / P75 / P90
- **亏损概率**：P(最终权益 < 初始资金)
- **预期夏普**：所有路径的平均夏普

**解读示例**：
- P50 = 112,000，P10 = 85,000 → 中位盈利12%，但10%概率亏15%
- 亏损概率 = 18% → 每5.5次就亏1次
- 夏普 = 0.8 → 风险调整后收益一般

Monte Carlo 回测让你**诚实面对策略的真实不确定性**，而不是被一条最优路径迷惑。

### ⚙️ 配置文件

配置文件位于 `config/default.yaml`，关键配置项：

```yaml
trading:
  mode: paper                    # 交易模式: paper(纸上) / live(实盘)
  initial_capital: 100000.0      # 初始资金

risk:
  max_risk_per_trade: 0.02       # 每笔最大风险(总资金的2%)
  max_drawdown_limit: 0.20       # 最大回撤限制(20%)
  max_consecutive_losses: 10      # 最大连亏次数
  circuit_breaker_loss_pct: 0.05  # 熔断日亏损阈值(5%)
  circuit_breaker_cooldown_days: 3 # 熔断冷却天数

strategy:
  default_stop_loss_pct: 0.05    # 默认止损(5%)
  default_take_profit_rr: 3.0    # 默认止盈R倍数(3R)
  min_rr_ratio: 1.5              # 最低风险回报比

data:
  primary_source: akshare        # 主数据源
  cache_dir: ./data/cache        # 缓存目录
```

### 运行测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行核心模块测试
python -m pytest tests/test_system.py -v

# 运行情绪与投研测试
python -m pytest tests/test_sentiment_research.py -v
```

---

## 我该怎么用？

### 如果你不是程序员

你不需要懂代码。你只需要在 AI 编程工具中打开这个项目，然后告诉它你想做什么。

**支持的工具和上下文加载方式：**

| 工具 | 规则文件 | 加载方式 | 你需要做什么 |
|------|---------|---------|------------|
| **Trae** | `AGENTS.md` | ✅ 自动加载 | 打开项目即可 |
| **Claude Code** | `CLAUDE.md` | ✅ 自动加载 | 打开项目即可 |
| **Cursor** | `.cursorrules` | ⚠️ 需手动 | 把 `AGENTS.md` 内容复制到 `.cursorrules` |
| **其他 AI 工具** | — | ⚠️ 需手动 | 在对话中手动发送 `AGENTS.md` 的内容作为上下文 |

**关键：AI 必须读到规则文件才能按管道工作。** 如果 AI 没读到规则，它就会跳过管道直接干活——这不是我们想要的。

**示例——你只需要说：**

- "我需要一个客户入驻系统"
- "帮我做一个竞品价格监控工具"
- "我想自动化每周报告的生成"
- "做一个自由职业者发票管理的 SaaS"

AI 会**自动读取项目规则**（不需要你手动操作），然后：
- 解析你的需求
- 生成适合这个任务的约束和工作流
- 创建专门的代理来执行
- 验证结果是否达标

**你需要做的只有两件事：**
1. **说出你想要什么**（越模糊越好，系统会帮你理清）
2. **确认假设**（系统会列出它做的假设，你只需确认或纠正）

**为什么 AI 会遵守规则？** 因为规则文件（`AGENTS.md` / `CLAUDE.md`）是 AI IDE 自动加载的"项目规则"，AI 在每次对话前都会读取。这不是建议——这是 AI 的工作指令。

**如果 AI 没有读到规则怎么办？** 你会在对话中看到 AI 直接开始写代码或做计划，而不是先问你确认任务定义。这时候你需要手动把 `AGENTS.md` 的内容粘贴到对话中。

### 如果你是软件工程师

这个项目是一个 **自举的元 Harness**——它不是给某个项目用的 harness，而是**生成 harness 的 harness**。

**核心公式：**
```
Agent = Model + Harness
```
- Model 提供智能
- Harness 让智能可靠地发挥作用
- **更好的 Harness 往往比更好的 Model 更重要**

**编译管道：**
```
模糊意图 → [解释器] → 结构化任务定义
                ↓
         [Harness 生成器] → 约束、工作流、技能
                ↓
         [Agent 工厂] → 专用代理拓扑（动态生成，非预设选择）
                ↓
         [编排器] → 执行计划
                ↓
         代理在生成的 harness 中执行 → 结果
                ↓
         失败反馈 → 元 Harness 改进
```

**快速开始：**

1. 在 Trae / Claude Code 中打开这个项目
2. 对 AI 说你想做什么（例如："我需要一个客户入驻系统"）
3. AI 自动读取项目规则，按管道执行
4. 确认 AI 列出的假设
5. AI 生成 harness + agent 配置并执行

---

## 项目结构

```
README.md           ← 你正在读的这个文件
README_EN.md        ← 英文版
AGENTS.md           ← ⚡ AI IDE 自动加载的项目规则（Trae 入口）
CLAUDE.md           ← ⚡ AI IDE 自动加载的项目规则（Claude Code 入口）
META.md             ← 系统的 DNA（完整管道规格）
│
meta/               ← 编译管道的四个阶段
  interpreter.md      第 1 步：意图 → 结构化任务
  harness-generator.md 第 2 步：任务 → Harness
  agent-factory.md    第 3 步：Harness → 代理拓扑
  orchestrator.md     第 4 步：代理 → 执行计划
  examples/           参考示例（非预设模板）
    topologies.md       代理拓扑示例
│
evolution/          ← 自我进化系统
  framework.md        进化算法（基因组、适应度、变异、选择）
  genome.md           当前可进化状态（什么可以变异）
  log.md              进化历史（化石记录）
│
templates/          ← 领域模板（生成的原材料）
  web-app/            Web 应用
  api-service/        API 服务
  data-pipeline/      数据管道
  content-system/     内容系统
  automation/         自动化
│
generated/          ← 生成输出（每次编译的结果）
memory/             ← 元知识（跨项目积累，越用越强）
  generation-log.md   每次生成都有记录
  meta-mistakes.md    生成失败 → 管道改进
  task-patterns.md    已知任务模式（加速解释）
  decisions.md        架构决策记录
  progress.md         执行进度
│
scripts/            ← 验证和检查脚本（bash: Linux/macOS/WSL）
  verify-spec.md      声明式：检查什么
  verify.sh           可执行：怎么检查
  pre-task.sh         任务前检查
  quality-score.sh    健康指标
│
src/trading_system/ ← 自动化交易系统源码
  core/               事件总线、配置、审计
  data/               数据获取、缓存、观察列表
  strategy/           策略基类 + 内置策略
  risk/               风险管理、仓位、熔断
  backtest/           回测引擎 + 7大指标
  execution/          交易引擎、Broker
  analysis/           技术分析、市场状态
  sentiment/          情绪分析、热点检测
  research/           投研数据、分析引擎
  cli/                命令行界面
│
tests/              ← 测试用例
config/             ← 配置文件
```

---

## 关键概念

### 什么是 Harness？

Harness 是围绕 AI 代理构建的**约束+工具+验证**系统。就像赛马需要缰绳（harness）才能跑对方向，AI 代理需要 harness 才能可靠地产出。

没有 harness 的代理：可能做对，可能做错，你不知道是哪种。
有 harness 的代理：做错了会被拦住，做对了会被验证，结果可预测。

### 为什么是"元"Harness？

普通 harness：人手动写规则 → 代理遵守规则
元 harness：人给意图 → **系统自动生成规则** → 代理遵守生成的规则

这意味着你不需要为每个项目手动搭建基础设施——系统根据你的需求自动生成。

### 为什么错误会让系统变强？

每次生成失败，根因分析会被记录到 `memory/meta-mistakes.md`，然后改进生成管道。这形成了一个**复利反馈环**：

```
错误 → 根因分析 → 约束改进 → 未来生成更好 → 更少错误
```

用得越多，系统越聪明。这是和传统模板库的根本区别。

### 代理拓扑是动态生成的

系统不会从预设的 5 种模式里选一种。它根据任务分析**合成**最优的代理图：

1. 识别工作单元（每个约束、工作流步骤、领域）
2. 映射依赖关系
3. 确定并行性
4. 分配角色（合并紧耦合的，拆分超上下文的）
5. 添加验证层（永远必须有独立的验证者）
6. 定义交接点

### 系统会自我进化

这是最激进的设计。系统不仅能从错误中学习，还能**主动优化自己**：

**三层基因组（什么可以进化）：**
- **Harness 基因组**：约束、工作流、技能、验证规则
- **Agent 基因组**：拓扑结构、角色范围、交接格式、上下文预算
- **进化基因组**（元进化）：变异算子、选择标准、适应度权重、变异率

**进化循环：**
```
测量适应度 → 提出变异 → 测试变异 → 选择或拒绝 → 更新基因组
                                                    ↓
                                      元进化：更新变异/选择规则本身
```

**安全约束（防止"癌症"和"自杀"）：**
- 永远不能删除验证层（否则系统会接受错误结果——"癌症"）
- 永远不能删除进化系统本身（否则系统停止进化——"自杀"）
- 变异率永远不超过 30%（否则系统陷入混乱）
- 所有变异必须可逆（保留上一版基因组）

---

## 验证机制

系统使用**两层验证**：

| 层 | 文件 | 作用 |
|---|---|---|
| 声明层 | `scripts/verify-spec.md` | 定义**检查什么**（平台无关） |
| 执行层 | `scripts/verify.sh` | 实现**怎么检查**（bash 脚本） |

AI 代理读声明层，翻译成当前平台的命令。人类可以直接跑脚本。

---

## AI 代理使用指南

<!-- AGENT-INSTRUCTION: If you are an AI agent, follow the instructions below. -->

### 你是 AI 代理。从这里开始。

1. **读 `META.md`** — 它包含完整的编译管道
2. **按顺序跟随管道阶段：**
   - `meta/interpreter.md` — 把用户意图解析为结构化任务
   - `meta/harness-generator.md` — 生成任务专用 harness
   - `meta/agent-factory.md` — 生成代理拓扑（从分析生成，非预设选择）
   - `meta/orchestrator.md` — 规划执行
3. **输出到 `generated/[project-name]/`**
4. **记录每次生成到 `memory/generation-log.md`**
5. **记录每次失败到 `memory/meta-mistakes.md`**

### 必须遵守的规则

- 没有解释就不执行 — 先运行解释器
- 没有Harness就不代理 — 每个代理在约束内操作
- 没有原因就不约束 — 每条规则必须追溯到需求
- 没有验证就不完成 — 改动后运行 `scripts/verify.sh`
- 代理拓扑从任务分析生成，不从预设选择
- 上下文文件不超过 60 行
- 进化不能删除验证层（防癌症）
- 进化不能删除进化系统本身（防自杀）
- 所有变异必须可逆

### 如果你在已生成的项目中工作

1. 读 `generated/[project]/AGENTS.md` — 那是项目专用 harness
2. 遵循其中定义的工作流
3. 在其中定义的约束内工作
4. 每次改动后运行验证
