import numpy as np
import pandas as pd
import pytest

from trading_system.strategy.base import SignalType
from trading_system.strategy.north_flow import NorthFlowStrategy
from trading_system.strategy.sector_rotation import SectorRotationStrategy


@pytest.fixture
def sample_price_data():
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


@pytest.fixture
def sample_sector_data():
    return pd.DataFrame([
        {"name": "白酒", "heat_score": 85, "change_pct": 3.5},
        {"name": "新能源", "heat_score": 75, "change_pct": 2.8},
        {"name": "半导体", "heat_score": 55, "change_pct": 1.2},
        {"name": "银行", "heat_score": 30, "change_pct": -0.5},
    ])


class TestSectorRotationStrategy:
    def test_generate_signals_with_hot_sector(self, sample_price_data, sample_sector_data):
        strategy = SectorRotationStrategy()
        signals = strategy.generate_signals(
            sample_price_data,
            sector_data=sample_sector_data,
            symbol="600519",
            in_hot_sector=True,
        )
        assert isinstance(signals, list)

    def test_no_signals_without_sector_data(self, sample_price_data):
        strategy = SectorRotationStrategy()
        signals = strategy.generate_signals(sample_price_data, symbol="600519")
        assert len(signals) == 0

    def test_strategy_name(self):
        strategy = SectorRotationStrategy()
        assert strategy.name == "sector_rotation"

    def test_identify_hot_sectors(self, sample_sector_data):
        strategy = SectorRotationStrategy(min_sector_heat=60)
        hot = strategy._identify_hot_sectors(sample_sector_data)
        assert len(hot) >= 1
        assert "白酒" in hot


class TestNorthFlowStrategy:
    def test_buy_signal_on_consecutive_inflow(self, sample_price_data):
        strategy = NorthFlowStrategy(consecutive_days=3, min_inflow=50.0)
        north_flow = [100.0, 80.0, 120.0]
        signals = strategy.generate_signals(
            sample_price_data,
            north_flow_data=north_flow,
            symbol="600519",
        )
        assert any(s.signal_type == SignalType.BUY for s in signals)

    def test_sell_signal_on_consecutive_outflow(self, sample_price_data):
        strategy = NorthFlowStrategy(consecutive_days=3, min_outflow=-50.0)
        north_flow = [-100.0, -80.0, -120.0]
        signals = strategy.generate_signals(
            sample_price_data,
            north_flow_data=north_flow,
            symbol="600519",
        )
        assert any(s.signal_type == SignalType.SELL for s in signals)

    def test_no_signal_mixed_flow(self, sample_price_data):
        strategy = NorthFlowStrategy(consecutive_days=3)
        north_flow = [100.0, -50.0, 80.0]
        signals = strategy.generate_signals(
            sample_price_data,
            north_flow_data=north_flow,
            symbol="600519",
        )
        assert len(signals) == 0

    def test_no_signal_without_north_flow_data(self, sample_price_data):
        strategy = NorthFlowStrategy()
        signals = strategy.generate_signals(sample_price_data, symbol="600519")
        assert len(signals) == 0

    def test_strategy_name(self):
        strategy = NorthFlowStrategy()
        assert strategy.name == "north_flow"
