# 交易系统优化路线图

> 来源：项目深度审查后的系统性改进方案
> 创建时间：2026-04-22

---

## 项目现状

- 43 个测试全部通过
- ruff 检测出 130 个代码规范问题
- 已完成前一轮优化（三层风控、追踪止损、通知推送等）

---

## 改进项详细设计

### P0-1：修复 live 模式处理

**当前问题**：
- `execution/engine.py` 第44-51行，无论 `mode` 是 `paper` 还是 `live`，都使用 `PaperBroker`
- 用户设置 `--mode live` 以为在实盘交易，实际仍是纸上交易，存在安全隐患

**优化方案**：
- live 模式抛出 `NotImplementedError` 并记录审计日志
- 明确告知用户实盘模式尚未实现

**改动范围**：
- `src/trading_system/execution/engine.py`

---

### P0-2：提取 PositionSizer 统一仓位计算逻辑

**当前问题**：
- `risk/manager.py:calculate_position_size` 和 `backtest/engine.py:_calc_position_size` 逻辑几乎完全相同
- 波动率乘数、回撤乘数、置信度乘数、100股取整等逻辑各自独立实现
- 违反 DRY 原则，修改一处而忘记另一处将导致回测与实盘行为不一致

**优化方案**：
- 提取 `PositionSizer` 类，封装仓位计算逻辑
- `RiskManager` 和 `BacktestEngine` 共用同一个 `PositionSizer`
- 确保回测和实盘的仓位计算完全一致

**改动范围**：
- 新增 `src/trading_system/risk/sizer.py`
- `src/trading_system/risk/manager.py` — 使用 PositionSizer
- `src/trading_system/backtest/engine.py` — 使用 PositionSizer

---

### P0-3：回测引擎使用 Position 模型替代 dict

**当前问题**：
- `backtest/engine.py` 第313行，回测持仓用 `dict[str, dict]` 表示
- 实盘用 `Position` dataclass，两者字段名和逻辑不一致
- 增加维护成本和出错概率

**优化方案**：
- 回测引擎中使用 `Position` dataclass 替代 `dict`
- 统一回测和实盘的数据模型

**改动范围**：
- `src/trading_system/backtest/engine.py`

---

### P0-4：修复信号聚合器时间匹配逻辑

**当前问题**：
- `strategy/aggregator.py` 第46行，信号聚合使用 `timestamp.isoformat()` 作为分组键
- 不同策略在同一时间点产生的信号，timestamp 可能有纳秒级差异
- 导致本应聚合的信号被分散到不同组

**优化方案**：
- 改用日期级别（`date`）作为分组键
- 同一交易日的同方向信号聚合在一起

**改动范围**：
- `src/trading_system/strategy/aggregator.py`

---

### P1-1：引入服务容器

**当前问题**：
- 整个系统缺少统一的依赖注入机制
- `TradingEngine` 硬编码创建 `DataStore`、`RiskManager`、`PaperBroker`、`NotificationManager`
- CLI 命令中到处手动创建实例，配置对象被重复创建

**优化方案**：
- 引入轻量级服务容器（字典注册模式）
- 统一管理组件创建和依赖注入
- 便于测试中替换真实依赖

**改动范围**：
- 新增 `src/trading_system/core/container.py`
- `src/trading_system/execution/engine.py`
- `src/trading_system/cli/main.py`

---

### P1-2：改进数据缓存策略

**当前问题**：
- `data/store.py` 缓存策略是"有缓存就用，没有就重新获取"
- 没有缓存过期机制（TTL）
- 没有增量更新（只获取新数据追加）
- 使用过期数据可能导致严重错误

**优化方案**：
- 添加 TTL 机制：日线数据缓存1天，实时数据不缓存
- 添加增量更新：如果缓存存在，只获取最后一条记录之后的数据
- 缓存元数据记录数据范围和过期时间

**改动范围**：
- `src/trading_system/data/store.py`

---

### P1-3：统一市场状态检测逻辑

**当前问题**：
- `detect_market_state` 在 `strategy/base.py` 和 `analysis/market.py` 中各有一份
- 逻辑不同：一个用波动率阈值 0.03，另一个用 ADX 指标
- 应该统一为一处

**优化方案**：
- 删除 `strategy/base.py` 中的 `detect_market_state`
- 统一使用 `analysis/market.py` 中基于 ADX 的版本
- `StrategyBase` 调用 `MarketAnalyzer.detect_state`

**改动范围**：
- `src/trading_system/strategy/base.py`
- `src/trading_system/analysis/market.py`

---

### P1-4：统一侧向类型（PositionSide 枚举）

**当前问题**：
- `Position.side` 用 `"long"/"short"` 字符串
- `Order.side` 用 `OrderSide.BUY/SELL` 枚举
- `Signal.signal_type` 用 `SignalType.BUY/SELL` 枚举
- 三种表示方式之间需要手动转换，容易出错

**优化方案**：
- 引入 `PositionSide` 枚举（LONG/SHORT）
- `Position` 使用 `PositionSide` 替代字符串
- 添加 `SignalType` → `PositionSide` 和 `OrderSide` → `PositionSide` 的转换方法

**改动范围**：
- `src/trading_system/strategy/base.py` — 新增 PositionSide
- `src/trading_system/risk/manager.py` — Position 使用 PositionSide
- `src/trading_system/execution/engine.py` — 转换逻辑
- `src/trading_system/backtest/engine.py` — 转换逻辑

---

### P1-5：添加异步交易循环

**当前问题**：
- `TradingEngine.start()` 只是设置 `_running = True`，没有实际的事件循环
- 真正的交易系统需要持续运行来获取行情、检查止损止盈、生成信号

**优化方案**：
- 实现 `run_loop()` 方法，包含定时循环
- 定时获取行情 → 检查持仓 → 生成信号 → 执行交易
- 支持优雅停止

**改动范围**：
- `src/trading_system/execution/engine.py`

---

### P1-6：增强新闻情绪分析

**当前问题**：
- `research/engine.py` 的新闻情绪分析仅基于关键词匹配
- 无法理解否定语境（如"增长不及预期"包含"增长"但实际是负面）
- 没有情绪强度区分

**优化方案**：
- 添加否定词检测：否定词 + 正面词 = 负面
- 添加情绪强度：根据关键词数量和位置加权
- 添加混合信号处理：正面和负面关键词同时出现时标记为"mixed"

**改动范围**：
- `src/trading_system/research/engine.py`

---

### P2-1：修复 130 个 ruff 错误

**当前问题**：
- 77 行超长（E501）
- 23 个未使用的导入（F401）
- 20 个未排序的导入（I001）
- 8 个 f-string 缺少插值（F541）
- 2 个未使用的变量（F841）

**优化方案**：
- 运行 `ruff check --fix` 自动修复可修复的
- 手动修复剩余问题

**改动范围**：
- 全部 `src/` 文件

---

### P2-2：补充缺失依赖

**当前问题**：
- `notification/channels.py` 使用 `httpx`，但 `pyproject.toml` 未声明
- `backtest/report.py` 使用 `matplotlib`，但未在 `optional-dependencies` 中声明

**优化方案**：
- 添加 `httpx` 到 `dependencies`
- 添加 `matplotlib` 到 `optional-dependencies` 的 `viz` 组

**改动范围**：
- `pyproject.toml`

---

### P2-3：补充测试

**当前问题**：
- 43 个测试只覆盖基本功能路径
- 没有测试 `SignalAggregator`、`NotificationManager`、`Reporting` 模块
- 没有边界条件测试

**优化方案**：
- 新增 aggregator 测试
- 新增 notification 测试
- 新增 reporting 测试
- 新增边界条件测试（空数据、极端波动、零资金等）
- 添加 `conftest.py` 统一管理 fixtures

**改动范围**：
- `tests/conftest.py`
- `tests/test_aggregator.py`
- `tests/test_notification.py`
- `tests/test_reporting.py`

---

### P2-4：添加日志配置初始化

**当前问题**：
- 项目各模块大量使用 `logging.getLogger(__name__)`，但没有统一的日志配置入口
- 默认只输出 WARNING 级别以上

**优化方案**：
- 新增 `core/logging.py`，提供 `setup_logging()` 函数
- CLI 入口调用 `setup_logging()`
- 支持配置文件指定日志级别和格式

**改动范围**：
- 新增 `src/trading_system/core/logging_config.py`
- `src/trading_system/cli/main.py`

---

### P2-5：完善 __init__.py 导出公共 API

**当前问题**：
- 所有 `__init__.py` 都是空文件
- 无法使用 `from trading_system.strategy import TrendFollowingStrategy`

**优化方案**：
- 各模块 `__init__.py` 导出核心类和函数

**改动范围**：
- 各模块 `__init__.py`

---

### P3-1：添加 trade stop 命令

**当前问题**：
- 有 `trading trade start` 没有 `trading trade stop`

**优化方案**：
- 添加 `trading trade stop` 命令
- 支持优雅停止交易引擎

**改动范围**：
- `src/trading_system/cli/main.py`
- `src/trading_system/execution/engine.py`

---

### P3-2：添加参数网格搜索工具

**当前问题**：
- 缺少策略参数优化工具

**优化方案**：
- 新增 `backtest/optimizer.py`
- 支持参数网格搜索
- 输出最优参数组合和绩效对比

**改动范围**：
- 新增 `src/trading_system/backtest/optimizer.py`
- `src/trading_system/cli/main.py`

---

### P3-3：实现数据库持久化

**当前问题**：
- `DataConfig.database_url` 配置了 SQLite URL，但 `DataStore` 完全没有使用 SQLAlchemy
- 交易记录、持仓历史等全部存在内存中，进程结束后丢失

**优化方案**：
- 使用 SQLAlchemy 存储交易记录和持仓历史
- 支持查询历史交易和绩效统计

**改动范围**：
- `src/trading_system/data/store.py`
- 新增 `src/trading_system/data/models.py`

---

## 实施状态

| 编号 | 优化项 | 优先级 | 状态 | 改动文件 |
|------|--------|--------|------|----------|
| P0-1 | 修复 live 模式处理 | 高 | ✅ 已完成 | `execution/engine.py` |
| P0-2 | 提取 PositionSizer | 高 | ✅ 已完成 | 新增 `risk/sizer.py`, `risk/manager.py`, `backtest/engine.py` |
| P0-3 | 回测引擎使用 Position 模型 | 高 | ✅ 已完成 | `backtest/engine.py` |
| P0-4 | 修复信号聚合器时间匹配 | 高 | ✅ 已完成 | `strategy/aggregator.py` |
| P1-1 | 引入服务容器 | 中 | ✅ 已完成 | 新增 `core/container.py`, `execution/engine.py`, `cli/main.py` |
| P1-2 | 改进数据缓存策略 | 中 | ✅ 已完成 | `data/store.py` |
| P1-3 | 统一市场状态检测 | 中 | ✅ 已完成 | `strategy/base.py`, `analysis/market.py` |
| P1-4 | 统一侧向类型 | 中 | ✅ 已完成 | `strategy/base.py`, `risk/manager.py`, `execution/engine.py`, `backtest/engine.py` |
| P1-5 | 添加异步交易循环 | 中 | ✅ 已完成 | `execution/engine.py` |
| P1-6 | 增强新闻情绪分析 | 中 | ✅ 已完成 | `research/engine.py` |
| P2-1 | 修复 ruff 错误 | 低 | ✅ 已完成 | 全部 `src/` 文件 (130→0) |
| P2-2 | 补充缺失依赖 | 低 | ✅ 已完成 | `pyproject.toml` |
| P2-3 | 补充测试 | 低 | ✅ 已完成 | `tests/` (43→62) |
| P2-4 | 添加日志配置 | 低 | ✅ 已完成 | 新增 `core/logging_config.py`, `cli/main.py` |
| P2-5 | 完善 __init__.py | 低 | ✅ 已完成 | 各模块 `__init__.py` |
| P3-1 | 添加 trade stop 命令 | 低 | ✅ 已完成 | `cli/main.py`, `execution/engine.py` |
| P3-2 | 添加参数网格搜索 | 低 | ✅ 已完成 | 新增 `backtest/optimizer.py` |
| P3-3 | 实现数据库持久化 | 低 | ✅ 已完成 | 新增 `data/models.py` |
