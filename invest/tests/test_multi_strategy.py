import numpy as np
import pandas as pd
import pytest

from trading_system.strategy.aggregator import AggregatedSignal, SignalAggregator
from trading_system.strategy.base import Signal, SignalType
from trading_system.strategy.north_flow import NorthFlowStrategy
from trading_system.strategy.sector_rotation import SectorRotationStrategy
from trading_system.strategy.strategies import TrendFollowingStrategy


@pytest.fixture
def sample_data():
    dates = pd.date_range(start="2024-01-10", periods=60, freq="B")
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(60) * 0.5)
    high = close + np.abs(np.random.randn(60) * 0.3)
    low = close - np.abs(np.random.randn(60) * 0.3)
    open_ = close + np.random.randn(60) * 0.2
    volume = np.random.randint(100000, 1000000, 60).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


class TestMultiStrategyAggregation:
    def test_register_ashare_strategies(self):
        agg = SignalAggregator()
        agg.register_strategy("trend_following", TrendFollowingStrategy())
        agg.register_strategy("sector_rotation", SectorRotationStrategy())
        agg.register_strategy("north_flow", NorthFlowStrategy())
        assert len(agg._strategies) == 3

    def test_three_strategy_resonance_high_confidence(self, sample_data):
        agg = SignalAggregator()
        agg.register_strategy("trend_following", TrendFollowingStrategy())
        agg.register_strategy("sector_rotation", SectorRotationStrategy())
        agg.register_strategy("north_flow", NorthFlowStrategy())

        pd.DataFrame([
            {"name": "白酒", "heat_score": 85, "change_pct": 3.5},
        ])

        results = agg.aggregate_signals(
            sample_data,
            symbol="600519",
        )
        for r in results:
            if r.strategy_count >= 3:
                assert r.confidence >= 0.9

    def test_needs_manual_review(self):
        sig = AggregatedSignal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            confidence=0.5,
            strategy_count=1,
            agreeing_strategies=["trend"],
            disagreeing_strategies=["north_flow"],
            original_signals=[
                Signal(symbol="600519", signal_type=SignalType.BUY, price=100.0, strategy_name="trend"),
                Signal(symbol="600519", signal_type=SignalType.SELL, price=100.0, strategy_name="north_flow"),
            ],
        )
        assert sig.needs_manual_review is True

    def test_no_manual_review_when_consensus(self):
        sig = AggregatedSignal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            confidence=0.8,
            strategy_count=2,
            agreeing_strategies=["trend", "sector"],
            disagreeing_strategies=[],
            original_signals=[
                Signal(symbol="600519", signal_type=SignalType.BUY, price=100.0, strategy_name="trend"),
                Signal(symbol="600519", signal_type=SignalType.BUY, price=100.0, strategy_name="sector"),
            ],
        )
        assert sig.needs_manual_review is False

    def test_consensus_strength_with_3_strategies(self):
        sig = AggregatedSignal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            confidence=0.7,
            strategy_count=3,
            agreeing_strategies=["a", "b", "c"],
            disagreeing_strategies=[],
        )
        assert sig.consensus_strength == "strong"
