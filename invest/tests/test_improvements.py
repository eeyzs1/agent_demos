from datetime import datetime

import pytest

from trading_system.strategy.aggregator import AggregatedSignal, SignalAggregator
from trading_system.strategy.base import PositionSide, Signal, SignalType
from trading_system.strategy.strategies import TrendFollowingStrategy


@pytest.fixture
def sample_signal_buy():
    return Signal(
        symbol="TEST",
        signal_type=SignalType.BUY,
        price=100.0,
        timestamp=datetime(2024, 1, 15, 10, 0, 0),
        stop_loss=95.0,
        take_profit=115.0,
        confidence=0.8,
        strategy_name="strategy_a",
    )


@pytest.fixture
def sample_signal_sell():
    return Signal(
        symbol="TEST",
        signal_type=SignalType.SELL,
        price=100.0,
        timestamp=datetime(2024, 1, 15, 10, 0, 0),
        stop_loss=105.0,
        take_profit=85.0,
        confidence=0.7,
        strategy_name="strategy_a",
    )


class TestPositionSide:
    def test_from_signal_buy(self):
        assert PositionSide.from_signal(SignalType.BUY) == PositionSide.LONG

    def test_from_signal_sell(self):
        assert PositionSide.from_signal(SignalType.SELL) == PositionSide.SHORT

    def test_string_value(self):
        assert PositionSide.LONG == "long"
        assert PositionSide.SHORT == "short"


class TestSignalAggregator:
    def test_empty_strategies(self):
        agg = SignalAggregator()
        result = agg.aggregate_signals(None, "TEST")
        assert result == []

    def test_single_strategy_signals(self, sample_signal_buy):
        strategy = TrendFollowingStrategy()
        agg = SignalAggregator({"trend": strategy})
        result = agg.to_signals(None, "TEST", min_consensus="weak")
        assert isinstance(result, list)

    def test_aggregated_signal_consensus(self):
        agg_sig = AggregatedSignal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=100.0,
            confidence=0.9,
            strategy_count=3,
            agreeing_strategies=["a", "b", "c"],
            disagreeing_strategies=[],
        )
        assert agg_sig.consensus_strength == "strong"

    def test_aggregated_signal_moderate(self):
        agg_sig = AggregatedSignal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=100.0,
            confidence=0.7,
            strategy_count=2,
            agreeing_strategies=["a", "b"],
            disagreeing_strategies=[],
        )
        assert agg_sig.consensus_strength == "moderate"

    def test_aggregated_signal_weak(self):
        agg_sig = AggregatedSignal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=100.0,
            confidence=0.4,
            strategy_count=1,
            agreeing_strategies=["a"],
            disagreeing_strategies=[],
        )
        assert agg_sig.consensus_strength == "weak"

    def test_date_level_grouping(self, sample_signal_buy):
        signal_later = Signal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=101.0,
            timestamp=datetime(2024, 1, 15, 14, 30, 0),
            stop_loss=96.0,
            take_profit=116.0,
            confidence=0.75,
            strategy_name="strategy_b",
        )
        agg = SignalAggregator()
        agg.register_strategy("a", TrendFollowingStrategy())
        agg.register_strategy("b", TrendFollowingStrategy())
        all_signals = {"2024-01-15": [("a", sample_signal_buy), ("b", signal_later)]}
        buy_signals = [
            (n, s) for n, s in all_signals.get("2024-01-15", []) if s.signal_type == SignalType.BUY
        ]
        assert len(buy_signals) == 2


class TestNotificationManager:
    def test_notification_manager_creation(self):
        from trading_system.core.config import NotificationConfig

        config = NotificationConfig()
        assert config is not None


class TestReporting:
    def test_daily_report_generation(self):
        from trading_system.core.config import RiskConfig
        from trading_system.reporting.daily import generate_daily_report
        from trading_system.risk.manager import RiskManager

        rm = RiskManager(RiskConfig(), initial_capital=100000.0)
        report = generate_daily_report(rm, 100000.0, output_dir="./output")
        assert isinstance(report, str)

    def test_weekly_report_generation(self):
        from trading_system.core.config import RiskConfig
        from trading_system.reporting.weekly import generate_weekly_report
        from trading_system.risk.manager import RiskManager

        rm = RiskManager(RiskConfig(), initial_capital=100000.0)
        report = generate_weekly_report(rm, 100000.0, output_dir="./output")
        assert isinstance(report, str)


class TestEdgeCases:
    def test_risk_manager_zero_equity(self):
        from trading_system.core.config import RiskConfig
        from trading_system.risk.manager import RiskManager

        rm = RiskManager(RiskConfig(), initial_capital=0.0)
        signal = Signal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=95.0,
            confidence=0.8,
            strategy_name="test",
        )
        valid, _ = rm.validate_signal(signal)
        assert not valid

    def test_risk_manager_no_stop_loss(self):
        from trading_system.core.config import RiskConfig
        from trading_system.risk.manager import RiskManager

        rm = RiskManager(RiskConfig(), initial_capital=100000.0)
        signal = Signal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=None,
            confidence=0.8,
            strategy_name="test",
        )
        valid, reason = rm.validate_signal(signal)
        assert not valid

    def test_position_sizer_zero_risk_per_share(self):
        from trading_system.core.config import RiskConfig
        from trading_system.risk.sizer import PositionSizer

        sizer = PositionSizer(RiskConfig(), 100000.0)
        signal = Signal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=100.0,
            confidence=0.8,
            strategy_name="test",
        )
        size = sizer.calculate_position_size(100000.0, signal, 0.0)
        assert size == 0.0

    def test_data_store_cache_expired(self):
        from trading_system.data.store import DataStore

        ds = DataStore()
        meta = {}
        assert ds._is_expired(meta, __import__("datetime").timedelta(hours=24))
        meta_no_time = {"rows": 10}
        assert ds._is_expired(meta_no_time, __import__("datetime").timedelta(hours=24))

    def test_container_basic_operations(self):
        from trading_system.core.container import ServiceContainer

        container = ServiceContainer()
        container.register_instance("test_service", "hello")
        assert container.get("test_service") == "hello"
        assert container.has("test_service")
        assert not container.has("nonexistent")
        container.remove("test_service")
        assert not container.has("test_service")

    def test_container_factory(self):
        from trading_system.core.container import ServiceContainer

        container = ServiceContainer()
        container.register_factory("counter", lambda: [0], singleton=True)
        a = container.get("counter")
        b = container.get("counter")
        assert a is b

    def test_container_missing_service(self):
        from trading_system.core.container import ServiceContainer

        container = ServiceContainer()
        with pytest.raises(KeyError):
            container.get("nonexistent")
