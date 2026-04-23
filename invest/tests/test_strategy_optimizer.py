import numpy as np
import pandas as pd
import pytest

from trading_system.backtest.optimizer import (
    GridOptimizer,
    OptimizationResult,
    StrategyOptimizer,
)


def _make_test_data(days: int = 200) -> pd.DataFrame:
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
def test_data():
    return _make_test_data()


class TestOptimizationResult:
    def test_top_n(self):
        results = [
            {"param": i, "sharpe_ratio": float(i)} for i in range(19, -1, -1)
        ]
        opt_result = OptimizationResult(
            strategy_name="test",
            method="grid_search",
            objective="sharpe_ratio",
            results=results,
            best_params={"param": 19},
            best_score=19.0,
        )
        top = opt_result.top_n(5)
        assert len(top) == 5
        assert top[0]["sharpe_ratio"] == 19.0

    def test_to_dataframe(self):
        results = [{"param": 1, "sharpe": 0.5}, {"param": 2, "sharpe": 0.8}]
        opt_result = OptimizationResult(
            strategy_name="test",
            method="grid_search",
            objective="sharpe",
            results=results,
        )
        df = opt_result.to_dataframe()
        assert len(df) == 2


class TestStrategyOptimizerGridSearch:
    def test_grid_search_basic(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10], "long_window": [20, 30]},
        )
        result = optimizer.grid_search(test_data, symbol="TEST", objective="sharpe_ratio")
        assert isinstance(result, OptimizationResult)
        assert result.method == "grid_search"
        assert result.objective == "sharpe_ratio"
        assert len(result.results) > 0

    def test_grid_search_best_params(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10], "long_window": [20, 30]},
        )
        result = optimizer.grid_search(test_data, symbol="TEST")
        assert "short_window" in result.best_params
        assert "long_window" in result.best_params

    def test_grid_search_invalid_objective(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5]},
        )
        with pytest.raises(ValueError, match="Invalid objective"):
            optimizer.grid_search(test_data, symbol="TEST", objective="invalid_metric")

    def test_grid_search_calmar_objective(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10], "long_window": [20, 30]},
        )
        result = optimizer.grid_search(test_data, symbol="TEST", objective="calmar_ratio")
        assert result.objective == "calmar_ratio"
        assert "calmar_ratio" in result.results[0]


class TestStrategyOptimizerRandomSearch:
    def test_random_search_basic(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10, 15, 20], "long_window": [20, 30, 40, 50]},
        )
        result = optimizer.random_search(
            test_data, symbol="TEST", objective="sharpe_ratio", n_trials=3, seed=42
        )
        assert isinstance(result, OptimizationResult)
        assert result.method == "random_search"
        assert len(result.results) > 0

    def test_random_search_with_seed(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10, 15], "long_window": [20, 30, 40]},
        )
        result1 = optimizer.random_search(
            test_data, symbol="TEST", n_trials=3, seed=42
        )
        result2 = optimizer.random_search(
            test_data, symbol="TEST", n_trials=3, seed=42
        )
        assert result1.best_params == result2.best_params

    def test_random_search_invalid_objective(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5]},
        )
        with pytest.raises(ValueError, match="Invalid objective"):
            optimizer.random_search(test_data, symbol="TEST", objective="bad")

    def test_random_search_n_trials(self, test_data):
        optimizer = StrategyOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10], "long_window": [20, 30]},
        )
        result = optimizer.random_search(
            test_data, symbol="TEST", n_trials=5, seed=42
        )
        assert len(result.results) <= 5


class TestGridOptimizerLegacy:
    def test_grid_optimizer_run(self, test_data):
        optimizer = GridOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10], "long_window": [20, 30]},
        )
        df = optimizer.run(test_data, symbol="TEST")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "sharpe_ratio" in df.columns

    def test_grid_optimizer_best_params(self, test_data):
        optimizer = GridOptimizer(
            strategy_name="trend_following",
            param_grid={"short_window": [5, 10], "long_window": [20, 30]},
        )
        params = optimizer.best_params(test_data, symbol="TEST")
        assert "short_window" in params
        assert "long_window" in params
