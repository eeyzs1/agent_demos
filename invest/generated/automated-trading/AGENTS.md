# Automated Trading System — Project Context

## Domain
Quantitative trading automation for retail investors (A-shares primary).

## Architecture
- `src/trading_system/core/` — Event bus, config, audit logging
- `src/trading_system/data/` — Market data (akshare/yfinance), watchlists
- `src/trading_system/strategy/` — Strategy base + 3 built-in strategies
- `src/trading_system/risk/` — Position sizing, stop-loss, drawdown, circuit breaker
- `src/trading_system/backtest/` — Engine + 7 metrics + rich reports
- `src/trading_system/execution/` — Paper broker, order management, trading engine
- `src/trading_system/analysis/` — Market state detection, technical indicators
- `src/trading_system/cli/` — Click CLI with rich terminal output

## Hard Constraints
1. Every trade MUST have stop-loss (enforced in RiskManager)
2. No live trading without backtest validation
3. Max drawdown limit enforced at system level
4. Paper trading mode before live
5. All actions logged with audit trail

## Key Metrics (7 Quantitative Indicators)
Win Rate, Risk/Reward Ratio, Max Drawdown, % Risk/Trade, Annual Return, Max Consecutive Losses, R-Multiple
