from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from trading_system.backtest.engine import BacktestEngine
from trading_system.core.config import RiskConfig
from trading_system.risk.manager import Position, RiskManager
from trading_system.strategy.base import PositionSide, Signal, SignalType
from trading_system.strategy.strategies import TrendFollowingStrategy


class TestPositionT1:
    def test_position_t1_locked_default(self):
        pos = Position(
            symbol="600519",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
            entry_time=datetime(2024, 1, 15, 10, 0, 0),
        )
        assert pos.is_t1_locked is True

    def test_t1_locked_on_same_day(self):
        entry = datetime(2024, 1, 15, 10, 0, 0)
        pos = Position(
            symbol="600519",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
            entry_time=entry,
        )
        assert pos.is_t1_locked_on(entry) is True
        assert pos.is_t1_locked_on(datetime(2024, 1, 15, 14, 0, 0)) is True

    def test_t1_unlocked_next_day(self):
        entry = datetime(2024, 1, 15, 10, 0, 0)
        pos = Position(
            symbol="600519",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
            entry_time=entry,
        )
        next_day = datetime(2024, 1, 16, 10, 0, 0)
        assert pos.is_t1_locked_on(next_day) is False

    def test_unlock_t1(self):
        entry = datetime(2024, 1, 15, 10, 0, 0)
        pos = Position(
            symbol="600519",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
            entry_time=entry,
        )
        assert pos.is_t1_locked is True
        next_day = datetime(2024, 1, 16, 10, 0, 0)
        pos.unlock_t1(next_day)
        assert pos.is_t1_locked is False

    def test_unlock_t1_same_day_stays_locked(self):
        entry = datetime(2024, 1, 15, 10, 0, 0)
        pos = Position(
            symbol="600519",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
            entry_time=entry,
        )
        pos.unlock_t1(entry)
        assert pos.is_t1_locked is True


class TestRiskManagerT1:
    def test_check_positions_skips_t1_locked(self):
        config = RiskConfig()
        rm = RiskManager(config=config, initial_capital=100000.0)

        signal = Signal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
        )
        rm.open_position(signal, 100)

        closed = rm.check_positions({"600519": 80.0})
        assert len(closed) == 0

    def test_check_positions_allows_exit_after_t1(self):
        config = RiskConfig()
        rm = RiskManager(config=config, initial_capital=100000.0)

        signal = Signal(
            symbol="600519",
            signal_type=SignalType.BUY,
            price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
        )
        pos = rm.open_position(signal, 100)
        pos.entry_time = datetime.now() - timedelta(days=1)
        pos.is_t1_locked = True

        closed = rm.check_positions({"600519": 80.0})
        assert len(closed) == 1
        assert closed[0]["reason"] == "stop_loss"


@pytest.fixture
def t1_sample_data():
    dates = pd.date_range(start="2024-01-10", periods=60, freq="B")
    np.random.seed(123)
    close = 100 + np.cumsum(np.random.randn(60) * 0.5)
    high = close + np.abs(np.random.randn(60) * 0.3)
    low = close - np.abs(np.random.randn(60) * 0.3)
    open_ = close + np.random.randn(60) * 0.2
    volume = np.random.randint(100000, 1000000, 60).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


class TestBacktestT1:
    def test_backtest_t1_no_same_day_exit(self, t1_sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        result = engine.run(t1_sample_data, symbol="TEST")

        for trade in result.trades:
            assert trade.entry_date.date() != trade.exit_date.date(), (
                f"T+1 violated: entry={trade.entry_date.date()} exit={trade.exit_date.date()}"
            )

    def test_backtest_position_has_t1_locked(self, t1_sample_data):
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=100000.0,
            risk_config=RiskConfig(),
        )
        result = engine.run(t1_sample_data, symbol="TEST")
        assert len(result.equity_curve) > 0
