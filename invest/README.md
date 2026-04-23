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
├── data/          市场数据获取(akshare/yfinance)、缓存、观察列表
├── strategy/      策略基类 + 3个内置策略
├── risk/          仓位计算、止损、最大回撤、熔断机制
├── backtest/      回测引擎 + 7大量化指标 + Rich报告
├── execution/     纸上交易Broker、订单管理、交易引擎
├── analysis/      市场状态检测(牛/熊/震荡)、技术指标
├── sentiment/     市场情绪分析、热点捕捉、持续性分析
├── research/      投研数据源(新闻/研报/公告)、投研引擎
└── cli/           Click命令行 + Rich终端界面
```

### 命令一览

| 命令组 | 命令 | 说明 |
|--------|------|------|
| `trading init` | — | 初始化项目目录和配置 |
| `trading data` | `fetch` | 获取股票日线数据 |
| `trading data` | `analyze` | 分析技术指标和市场状态 |
| `trading watchlist` | `create` | 创建观察列表 |
| `trading watchlist` | `add` | 添加股票到观察列表 |
| `trading watchlist` | `list` | 列出所有观察列表 |
| `trading strategy` | `list` | 列出可用策略 |
| `trading strategy` | `backtest` | 回测指定策略 |
| `trading sentiment` | `analyze` | 分析市场情绪 |
| `trading sentiment` | `hotspot` | 捕捉市场热点 |
| `trading sentiment` | `persistence` | 分析热点持续性 |
| `trading research` | `symbol` | 个股投研分析 |
| `trading research` | `market` | 全市场投研概览 |
| `trading trade` | `status` | 查看交易系统状态 |
| `trading trade` | `start` | 启动交易引擎 |

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
