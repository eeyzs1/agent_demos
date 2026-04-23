import numpy as np
import pandas as pd
import pytest

from trading_system.backtest.engine import BacktestEngine
from trading_system.core.config import RiskConfig
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


class TestAShareBacktest:
    def test_ashare_summary_present(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        result = engine.run(sample_data, symbol="600519")
        summary = result.ashare_summary
        assert "t1_blocked_count" in summary
        assert "total_cost" in summary
        assert "net_pnl_after_cost" in summary
        assert "gross_pnl_before_cost" in summary
        assert "total_stamp_tax" in summary
        assert "total_buy_commission" in summary
        assert "total_sell_commission" in summary

    def test_t1_blocked_count_tracked(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        result = engine.run(sample_data, symbol="600519")
        assert isinstance(result.t1_blocked_count, int)
        assert result.t1_blocked_count >= 0

    def test_cost_breakdown_non_negative(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        result = engine.run(sample_data, symbol="600519")
        assert result.total_buy_commission >= 0
        assert result.total_sell_commission >= 0
        assert result.total_stamp_tax >= 0
        assert result.total_transfer_fee >= 0

    def test_net_pnl_less_than_gross(self, sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        result = engine.run(sample_data, symbol="600519")
        summary = result.ashare_summary
        if result.total_trades > 0:
            assert summary["net_pnl_after_cost"] <= summary["gross_pnl_before_cost"]
