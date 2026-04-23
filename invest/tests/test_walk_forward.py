import numpy as np
import pandas as pd
import pytest

from trading_system.backtest.engine import BacktestEngine
from trading_system.core.config import RiskConfig
from trading_system.strategy.strategies import TrendFollowingStrategy


@pytest.fixture
def sample_data():
    dates = pd.date_range(start="2024-01-10", periods=120, freq="B")
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(120) * 0.5)
    high = close + np.abs(np.random.randn(120) * 0.3)
    low = close - np.abs(np.random.randn(120) * 0.3)
    open_ = close + np.random.randn(120) * 0.2
    volume = np.random.randint(100000, 1000000, 120).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


class TestWalkForward:
    def test_walk_forward_returns_results(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        results = engine.walk_forward(sample_data, symbol="600519")
        assert len(results) > 0

    def test_walk_forward_has_overfitting_risk(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        results = engine.walk_forward(sample_data, symbol="600519")
        for r in results:
            assert "overfitting_risk" in r
            assert r["overfitting_risk"] in ("low", "medium", "high")

    def test_walk_forward_has_ashare_summary(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        results = engine.walk_forward(sample_data, symbol="600519")
        for r in results:
            assert "train_ashare" in r
            assert "test_ashare" in r

    def test_walk_forward_window_structure(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        results = engine.walk_forward(sample_data, symbol="600519")
        for r in results:
            assert "window" in r
            assert "train_period" in r
            assert "test_period" in r
            assert "train_return" in r
            assert "test_return" in r
