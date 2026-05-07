# 自动化交易系统 — Quick Start

## 1. 环境准备

```bash
# Python ≥ 3.10
python --version

# 安装依赖
pip install -e .               # 核心依赖
pip install -e ".[dev,viz]"    # 加上测试和可视化
```

## 2. 项目结构

```
invest/
├── config/default.yaml ← 非敏感配置（策略参数、风控阈值）
├── .env                ← 敏感配置（密钥、账号密码，需自己创建）
├── .env.example        ← .env 模板
├── src/trading_system/
│   ├── strategy/       ← 策略（趋势、均值回归、突破、配对交易）
│   ├── backtest/       ← 回测引擎 + 蒙特卡洛 + 统计检验
│   ├── execution/      ← 交易引擎 + QMT/纸面经纪人
│   ├── risk/           ← 风险管理 + 仓位计算 + 熔断
│   ├── data/           ← 数据获取（akshare）+ 缓存 + 自选股
│   ├── analysis/       ← 行情分析 + RSI/ATR/ADX 共享指标
│   ├── portfolio/      ← 组合优化 + 因子模型 + 风险平价
│   ├── ml/             ← HMM/卡尔曼滤波/GARCH 波动率
│   ├── research/       ← 研报聚合引擎
│   ├── notification/   ← 飞书/钉钉/微信消息推送
│   └── cli/            ← 命令行入口
├── tests/              ← 测试
├── scripts/            ← 辅助脚本
├── logs/               ← 运行日志（自动生成）
└── data/cache/         ← 数据缓存（自动生成）
```

## 3. 配置

### 三步完成配置

```bash
# Step 1: 复制模板
cp .env.example .env

# Step 2: 编辑 .env（仅实盘需要，纸面交易跳过）
# 填入 QMT 路径和账号。通知是可选的，不填也能跑。

# Step 3: 确认 config/default.yaml 中 mode 正确
# paper = 纸面模拟 | qmt = 实盘
```

### YAML vs .env 分工

| 放哪里 | 内容 | 示例 |
|--------|------|------|
| `config/default.yaml` | 非敏感参数 | 风控比例、策略参数、数据源 |
| `.env` | 密钥和账号 | QMT 密码、webhook secret |

`.env` 不受 git 追踪，不会泄露。

## 4. 命令行

```bash
trading --help                 # 查看所有命令

# --- 数据 ---
trading data fetch 000001      # 获取平安银行日线
trading data fetch 000001 --save

# --- 策略 ---
trading strategy list          # 列出所有可用策略
trading strategy info trend    # 查看趋势策略详情

# --- 回测 ---
trading backtest run trend 000001 --start 20230101 --end 20240101
trading backtest montecarlo trend 000001 --start 20230101 --end 20240101
trading backtest report        # 查看最近回测报告

# --- 行情 ---
trading market analyze 000001  # 分析当前行情状态
trading market sentiment       # 市场情绪概览

# --- 运行 ---
trading run                    # 启动交易引擎
```

## 5. 可用策略

| 名称 | 策略 | 适用行情 |
|------|------|----------|
| `trend` | 双均线趋势跟踪（SMA + ATR 止损） | 牛市、熊市 |
| `mean_reversion` | 布林带均值回归 + RSI 过滤 | 震荡市 |
| `breakout` | 通道突破 + 成交量确认 | 牛市、突破 |
| `pairs` | 配对交易（协整 + 卡尔曼滤波） | 套利 |

## 6. 纸面交易验证（推荐第一步）

默认 `config/default.yaml` 中 `trading.mode: paper`，所有订单本地模拟，不产生真实资金变动。

```bash
trading run
```

运行后日志在 `./logs/trades.jsonl` 和 `./logs/audit.jsonl`。

## 7. QMT 实盘交易

```bash
# 1. 确保 QMT 客户端已登录
# 2. 编辑 .env:
#    QMT_PATH=C:\国金证券QMT交易端\userdata_mini
#    QMT_ACCOUNT=你的资金账号
# 3. 改 config/default.yaml: trading.mode: qmt
# 4. 启动
trading run
```

QMT 连接失败会自动回退到 paper 模式。

### 实盘风控检查清单

- [ ] 熔断保护已开启（默认：日亏 5% 熔断 3 天）
- [ ] 单笔最大风险 2%（`max_risk_per_trade`）
- [ ] 最大回撤 20% 硬止损（`max_drawdown_limit`）
- [ ] T+1 锁定保护（A 股今日买入不可卖出）
- [ ] 不支持做空（A 股 SELL = 平多）
- [ ] 涨跌停板截断

## 8. A 股特殊规则（已内置处理）

| 规则 | 处理方式 |
|------|----------|
| T+1 交割 | 持仓次日才能卖出 |
| 不允许做空 | SELL 信号 = 平掉多头，无持仓时拒绝 |
| 100 股整数倍 | 仓位自动向下取整到 100 的倍数 |
| 涨跌停板 | 价格自动 clamp 到涨跌停范围内 |
| 印花税 | 卖出时单向征收 0.05%（A 股成本模型） |

## 9. 目录初始化

首次运行会自动创建：
```
logs/
data/cache/
```
无需手动创建。
