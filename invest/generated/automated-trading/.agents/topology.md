# Agent Topology: Automated Trading System

## Topology Pattern: Planner → [Specialists] → Verifier

```
[Research Agent] ──→ [Strategy Agent] ──→ [Risk Agent] ──→ [Execution Agent]
       │                    │                   │                   │
       └────────────────────┴───────────────────┴──────────────────┘
                                    │
                            [Audit Verifier]
```

## Agent Definitions

### 1. Research Agent
- **Role**: Market data acquisition and analysis
- **Capabilities**: Fetch OHLCV data, calculate indicators, detect market state
- **Scope**: data/, analysis/
- **Tools**: DataStore, MarketAnalyzer
- **Handoff**: Market data + analysis → Strategy Agent

### 2. Strategy Agent
- **Role**: Signal generation based on market data
- **Capabilities**: Run strategies, generate buy/sell signals with SL/TP
- **Scope**: strategy/
- **Tools**: StrategyBase, Strategy Registry
- **Handoff**: Signals with R-multiple → Risk Agent

### 3. Risk Agent
- **Role**: Risk validation and position sizing
- **Capabilities**: Validate signals, calculate position size, enforce constraints
- **Scope**: risk/
- **Tools**: RiskManager, RiskConfig
- **Handoff**: Approved orders → Execution Agent

### 4. Execution Agent
- **Role**: Order submission and position monitoring
- **Capabilities**: Submit orders, monitor SL/TP, manage positions
- **Scope**: execution/
- **Tools**: TradingEngine, PaperBroker
- **Handoff**: Trade results → Audit Verifier

### 5. Audit Verifier
- **Role**: Verify all actions comply with constraints
- **Capabilities**: Check audit logs, validate risk limits, verify SL on every trade
- **Scope**: core/audit, all modules
- **Tools**: AuditLogger
- **Self-check**: Every trade has SL, no trade without backtest, drawdown within limits
