
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv():
    dates = pd.date_range(start="2023-01-01", periods=200, freq="B")
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(200) * 0.5)
    high = close + np.abs(np.random.randn(200) * 0.3)
    low = close - np.abs(np.random.randn(200) * 0.3)
    open_ = close + np.random.randn(200) * 0.2
    volume = np.random.randint(100000, 1000000, 200).astype(float)

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


class TestConfig:
    def test_default_config(self):
        from trading_system.core.config import AppConfig

        config = AppConfig()
        assert config.trading.mode == "paper"
        assert config.trading.initial_capital == 100000.0
        assert config.risk.max_risk_per_trade == 0.02
        assert config.risk.max_drawdown_limit == 0.20

    def test_config_validation(self):
        from pydantic import ValidationError

        from trading_system.core.config import RiskConfig

        with pytest.raises(ValidationError):
            RiskConfig(max_risk_per_trade=0.5)

    def test_config_from_yaml(self, tmp_path):
        from trading_system.core.config import AppConfig

        config_path = tmp_path / "test.yaml"
        AppConfig.save_default(config_path)
        loaded = AppConfig.from_yaml(config_path)
        assert loaded.trading.mode == "paper"


class TestEventBus:
    def test_publish_subscribe(self):
        from trading_system.core.events import Event, EventBus, EventType

        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.SIGNAL_GENERATED, handler)
        bus.publish_sync(Event(type=EventType.SIGNAL_GENERATED, data={"symbol": "TEST"}))

        assert len(received) == 1
        assert received[0].data["symbol"] == "TEST"

    def test_unsubscribe(self):
        from trading_system.core.events import Event, EventBus, EventType

        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.SIGNAL_GENERATED, handler)
        bus.unsubscribe(EventType.SIGNAL_GENERATED, handler)
        bus.publish_sync(Event(type=EventType.SIGNAL_GENERATED))

        assert len(received) == 0

    def test_history(self):
        from trading_system.core.events import Event, EventBus, EventType

        bus = EventBus()
        bus.publish_sync(Event(type=EventType.SIGNAL_GENERATED))
        bus.publish_sync(Event(type=EventType.ORDER_CREATED))

        assert len(bus.get_history()) == 2
        assert len(bus.get_history(EventType.SIGNAL_GENERATED)) == 1


class TestAuditLogger:
    def test_log_action(self, tmp_path):
        from trading_system.core.audit import AuditLogger

        logger = AuditLogger(log_dir=str(tmp_path))
        logger.log_action("test_action", "test_actor", {"key": "value"})

        entries = logger.read_audit_log()
        assert len(entries) == 1
        assert entries[0]["action"] == "test_action"

    def test_log_trade(self, tmp_path):
        from trading_system.core.audit import AuditLogger

        logger = AuditLogger(log_dir=str(tmp_path))
        logger.log_trade(
            trade_id="T001",
            symbol="600519",
            side="BUY",
            quantity=100,
            price=1800.0,
            strategy="trend_following",
        )

        entries = logger.read_trade_log()
        assert len(entries) == 1
        assert entries[0]["symbol"] == "600519"


class TestWatchlist:
    def test_create_and_add(self, tmp_path):
        from trading_system.data.watchlist import WatchlistManager

        manager = WatchlistManager(data_dir=str(tmp_path))
        manager.create("test_list")
        manager.add_symbol("test_list", "600519", "贵州茅台")

        symbols = manager.get_symbols("test_list")
        assert "600519" in symbols

    def test_list_all(self, tmp_path):
        from trading_system.data.watchlist import WatchlistManager

        manager = WatchlistManager(data_dir=str(tmp_path))
        manager.create("list1")
        manager.create("list2")

        all_lists = manager.list_all()
        assert len(all_lists) == 2


class TestStrategies:
    def test_trend_following_generates_signals(self, sample_ohlcv):
        from trading_system.strategy.base import SignalType
        from trading_system.strategy.strategies import TrendFollowingStrategy

        strategy = TrendFollowingStrategy()
        signals = strategy.generate_signals(sample_ohlcv)

        assert isinstance(signals, list)
        for sig in signals:
            assert sig.signal_type in (SignalType.BUY, SignalType.SELL)
            assert sig.stop_loss is not None
            assert sig.take_profit is not None

    def test_mean_reversion_generates_signals(self, sample_ohlcv):
        from trading_system.strategy.strategies import MeanReversionStrategy

        strategy = MeanReversionStrategy()
        signals = strategy.generate_signals(sample_ohlcv)
        assert isinstance(signals, list)

    def test_breakout_generates_signals(self, sample_ohlcv):
        from trading_system.strategy.strategies import BreakoutStrategy

        strategy = BreakoutStrategy()
        signals = strategy.generate_signals(sample_ohlcv)
        assert isinstance(signals, list)

    def test_strategy_registry(self):
        from trading_system.strategy.strategies import STRATEGY_REGISTRY, create_strategy

        for name in STRATEGY_REGISTRY:
            strat = create_strategy(name)
            desc = strat.describe()
            assert "name" in desc
            assert "type" in desc


class TestRiskManager:
    def test_position_sizing(self):
        from trading_system.core.config import RiskConfig
        from trading_system.risk.manager import RiskManager
        from trading_system.strategy.base import Signal, SignalType

        config = RiskConfig(max_risk_per_trade=0.02)
        rm = RiskManager(config=config, initial_capital=100000.0)

        signal = Signal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
        )

        quantity = rm.calculate_position_size(signal)
        assert quantity > 0
        assert quantity % 100 == 0

    def test_signal_validation_rejects_no_stop_loss(self):
        from trading_system.core.config import RiskConfig
        from trading_system.risk.manager import RiskManager
        from trading_system.strategy.base import Signal, SignalType

        config = RiskConfig()
        rm = RiskManager(config=config, initial_capital=100000.0)

        signal = Signal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=None,
        )

        valid, reason = rm.validate_signal(signal)
        assert not valid
        assert "stop-loss" in reason.lower()

    def test_circuit_breaker(self):
        from trading_system.core.config import RiskConfig
        from trading_system.risk.manager import RiskManager
        from trading_system.strategy.base import Signal, SignalType

        config = RiskConfig(circuit_breaker_loss_pct=0.01, circuit_breaker_cooldown_days=1)
        rm = RiskManager(config=config, initial_capital=100000.0)

        signal = Signal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
        )

        valid, _ = rm.validate_signal(signal)
        assert valid

        rm.open_position(signal, 100)
        rm.close_position("600519", 90.0, "manual")

        state = rm.get_state()
        assert state.consecutive_losses >= 1


class TestBacktestEngine:
    def test_backtest_produces_results(self, sample_ohlcv):
        from trading_system.backtest.engine import BacktestEngine
        from trading_system.core.config import RiskConfig
        from trading_system.strategy.strategies import TrendFollowingStrategy

        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )

        result = engine.run(sample_ohlcv, symbol="TEST")

        assert len(result.equity_curve) > 0
        assert len(result.dates) > 0

    def test_seven_metrics_calculated(self, sample_ohlcv):
        from trading_system.backtest.engine import BacktestEngine
        from trading_system.core.config import RiskConfig
        from trading_system.strategy.strategies import TrendFollowingStrategy

        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )

        result = engine.run(sample_ohlcv, symbol="TEST")
        metrics = result.get_seven_metrics(100000.0)

        required_keys = [
            "win_rate",
            "risk_reward_ratio",
            "max_drawdown",
            "risk_per_trade_pct",
            "annualized_return",
            "max_consecutive_losses",
            "avg_r_multiple",
        ]
        for key in required_keys:
            assert key in metrics, f"Missing metric: {key}"

    def test_backtest_summary(self, sample_ohlcv):
        from trading_system.backtest.engine import BacktestEngine
        from trading_system.core.config import RiskConfig
        from trading_system.strategy.strategies import TrendFollowingStrategy

        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )

        result = engine.run(sample_ohlcv, symbol="TEST")
        summary = result.summary(100000.0)

        assert "seven_key_metrics" in summary
        assert "total_trades" in summary
        assert "sharpe_ratio" in summary
        assert "profit_factor" in summary


class TestMarketAnalyzer:
    def test_detect_state(self, sample_ohlcv):
        from trading_system.analysis.market import MarketAnalyzer
        from trading_system.strategy.base import MarketState

        state = MarketAnalyzer.detect_state(sample_ohlcv)
        assert state in list(MarketState)

    def test_calculate_indicators(self, sample_ohlcv):
        from trading_system.analysis.market import MarketAnalyzer

        result = MarketAnalyzer.calculate_indicators(sample_ohlcv)
        assert "rsi_14" in result.columns
        assert "macd" in result.columns
        assert "atr_14" in result.columns
        assert "bb_upper" in result.columns
        assert "bb_lower" in result.columns

    def test_analyze_symbol(self, sample_ohlcv):
        from trading_system.analysis.market import MarketAnalyzer

        result = MarketAnalyzer.analyze_symbol(sample_ohlcv)
        assert "market_state" in result
        assert "current_price" in result
        assert "signals" in result


class TestPaperBroker:
    def test_submit_market_order(self):
        from trading_system.execution.broker import Order, OrderSide, OrderType, PaperBroker

        broker = PaperBroker(initial_capital=100000.0)
        order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=100.0,
        )

        filled = broker.submit_order(order)
        assert filled.is_filled
        assert filled.filled_price > 0

    def test_account_balance(self):
        from trading_system.execution.broker import Order, OrderSide, OrderType, PaperBroker

        broker = PaperBroker(initial_capital=100000.0)
        order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=100.0,
        )
        broker.submit_order(order)

        balance = broker.get_account_balance()
        assert balance["cash"] < 100000.0
        assert balance["total_equity"] > 0
