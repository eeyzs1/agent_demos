import numpy as np
import pandas as pd
import pytest

from trading_system.backtest.benchmark import (
    BENCHMARK_HS300,
    BenchmarkCalculator,
    BenchmarkResult,
    LookaheadBiasChecker,
)
from trading_system.backtest.engine import BacktestEngine, BacktestResult
from trading_system.strategy.strategies import create_strategy


def _make_benchmark_data(days: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", periods=days)
    close = 3000.0 + np.cumsum(np.random.randn(days) * 10)
    close = np.maximum(close, 1000.0)
    return pd.DataFrame({"close": close}, index=dates)


def _make_strategy_data(days: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", periods=days)
    close = 10.0 + np.cumsum(np.random.randn(days) * 0.1)
    close = np.maximum(close, 1.0)
    high = close * (1 + np.abs(np.random.randn(days) * 0.01))
    low = close * (1 - np.abs(np.random.randn(days) * 0.01))
    volume = np.random.randint(100000, 500000, size=days).astype(float)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def benchmark_data():
    return _make_benchmark_data()


@pytest.fixture
def strategy_data():
    return _make_strategy_data()


class TestBenchmarkCalculator:
    def test_calculate_from_data(self, benchmark_data):
        calc = BenchmarkCalculator()
        equity_curve = [100000.0 + i * 100 for i in range(100)]
        dates = list(range(100))
        result = calc.calculate_from_data(
            benchmark_data, equity_curve, dates, BENCHMARK_HS300
        )
        assert isinstance(result, BenchmarkResult)
        assert result.benchmark_name == BENCHMARK_HS300

    def test_alpha_calculation(self, benchmark_data):
        calc = BenchmarkCalculator()
        equity_curve = [100000.0 + i * 200 for i in range(100)]
        dates = list(range(100))
        result = calc.calculate_from_data(
            benchmark_data, equity_curve, dates
        )
        assert isinstance(result.alpha, float)

    def test_information_ratio(self, benchmark_data):
        calc = BenchmarkCalculator()
        equity_curve = [100000.0 + i * 100 for i in range(100)]
        dates = list(range(100))
        result = calc.calculate_from_data(
            benchmark_data, equity_curve, dates
        )
        assert isinstance(result.information_ratio, float)

    def test_beta_calculation(self, benchmark_data):
        calc = BenchmarkCalculator()
        equity_curve = [100000.0 + i * 100 for i in range(100)]
        dates = list(range(100))
        result = calc.calculate_from_data(
            benchmark_data, equity_curve, dates
        )
        assert isinstance(result.beta, float)

    def test_empty_data(self):
        calc = BenchmarkCalculator()
        empty_df = pd.DataFrame()
        result = calc.calculate_from_data(empty_df, [100000], [0])
        assert result.total_return_pct == 0.0

    def test_compare_with_benchmark(self):
        calc = BenchmarkCalculator()
        strategy_summary = {"total_return_pct": 15.0, "sharpe_ratio": 1.2, "max_drawdown": 8.0}
        benchmark = BenchmarkResult(
            benchmark_name=BENCHMARK_HS300,
            total_return_pct=10.0,
            sharpe_ratio=0.8,
            max_drawdown_pct=12.0,
            alpha=0.05,
            information_ratio=0.3,
            beta=0.9,
        )
        comparison = calc.compare_with_benchmark(strategy_summary, benchmark)
        assert comparison["excess_return_pct"] == 5.0
        assert comparison["outperforms"] is True

    def test_compare_underperforms(self):
        calc = BenchmarkCalculator()
        strategy_summary = {"total_return_pct": 5.0, "sharpe_ratio": 0.5, "max_drawdown": 15.0}
        benchmark = BenchmarkResult(
            benchmark_name=BENCHMARK_HS300,
            total_return_pct=10.0,
            sharpe_ratio=0.8,
            max_drawdown_pct=8.0,
        )
        comparison = calc.compare_with_benchmark(strategy_summary, benchmark)
        assert comparison["excess_return_pct"] == -5.0
        assert comparison["outperforms"] is False


class TestBenchmarkResult:
    def test_to_dict(self):
        result = BenchmarkResult(
            benchmark_name=BENCHMARK_HS300,
            total_return_pct=10.5,
            annualized_return_pct=12.3,
            sharpe_ratio=1.5,
            max_drawdown_pct=8.0,
            alpha=0.05,
            information_ratio=0.3,
            tracking_error=0.1,
            beta=0.9,
        )
        d = result.to_dict()
        assert d["benchmark_name"] == BENCHMARK_HS300
        assert d["benchmark_display_name"] == "沪深300"
        assert "total_return_pct" in d
        assert "alpha" in d


class TestLookaheadBiasChecker:
    def test_no_bias(self):
        checker = LookaheadBiasChecker()
        signals = [
            {"date": "2024-01-02", "price": 10.0, "close": 10.5},
            {"date": "2024-01-03", "price": 10.2, "close": 10.8},
        ]
        count = checker.check_signal_uses_same_day_close(signals)
        assert count == 0
        assert checker.is_clean()

    def test_detected_bias(self):
        checker = LookaheadBiasChecker()
        signals = [
            {"date": "2024-01-02", "price": 10.5, "close": 10.5},
        ]
        count = checker.check_signal_uses_same_day_close(signals)
        assert count == 1
        assert not checker.is_clean()

    def test_get_report(self):
        checker = LookaheadBiasChecker()
        signals = [
            {"date": "2024-01-02", "price": 10.5, "close": 10.5},
        ]
        checker.check_signal_uses_same_day_close(signals)
        report = checker.get_report()
        assert "is_clean" in report
        assert "issue_count" in report
        assert not report["is_clean"]

    def test_clean_report(self):
        checker = LookaheadBiasChecker()
        report = checker.get_report()
        assert report["is_clean"]
        assert report["issue_count"] == 0


class TestBacktestEngineLookaheadFix:
    def test_backtest_result_has_benchmark_field(self):
        result = BacktestResult()
        assert hasattr(result, "benchmark")
        assert result.benchmark is None

    def test_engine_has_use_open_for_signal(self, strategy_data):
        strategy = create_strategy("trend_following", {"short_window": 5, "long_window": 20})
        engine = BacktestEngine(strategy, use_open_for_signal=True)
        assert engine._use_open_for_signal is True

    def test_engine_default_use_open(self, strategy_data):
        strategy = create_strategy("trend_following", {"short_window": 5, "long_window": 20})
        engine = BacktestEngine(strategy)
        assert engine._use_open_for_signal is True

    def test_backtest_with_open_price(self, strategy_data):
        strategy = create_strategy("trend_following", {"short_window": 5, "long_window": 20})
        engine = BacktestEngine(strategy, use_open_for_signal=True)
        result = engine.run(strategy_data, symbol="TEST")
        assert isinstance(result, BacktestResult)

    def test_backtest_without_open_price(self, strategy_data):
        strategy = create_strategy("trend_following", {"short_window": 5, "long_window": 20})
        engine = BacktestEngine(strategy, use_open_for_signal=False)
        result = engine.run(strategy_data, symbol="TEST")
        assert isinstance(result, BacktestResult)
