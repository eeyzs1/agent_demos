import logging
import random
from dataclasses import dataclass, field
from itertools import product
from typing import Optional

import pandas as pd

from trading_system.backtest.engine import BacktestEngine
from trading_system.core.config import RiskConfig
from trading_system.strategy.strategies import create_strategy

logger = logging.getLogger(__name__)


class GridOptimizer:
    def __init__(
        self,
        strategy_name: str,
        param_grid: dict[str, list],
        initial_capital: float = 100000.0,
        risk_config: Optional[RiskConfig] = None,
        commission_rate: float = 0.0003,
        slippage_pct: float = 0.001,
    ):
        self._strategy_name = strategy_name
        self._param_grid = param_grid
        self._initial_capital = initial_capital
        self._risk_config = risk_config or RiskConfig()
        self._commission_rate = commission_rate
        self._slippage_pct = slippage_pct

    def run(self, data: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
        keys = list(self._param_grid.keys())
        values = list(self._param_grid.values())
        combinations = list(product(*values))

        results = []
        total = len(combinations)

        for idx, combo in enumerate(combinations, 1):
            params = dict(zip(keys, combo))
            try:
                strategy = create_strategy(self._strategy_name, params)
                engine = BacktestEngine(
                    strategy=strategy,
                    initial_capital=self._initial_capital,
                    risk_config=self._risk_config,
                    commission_rate=self._commission_rate,
                    slippage_pct=self._slippage_pct,
                )
                result = engine.run(data, symbol)

                metrics = result.get_seven_metrics(self._initial_capital)
                row = {
                    **params,
                    "total_return_pct": round(result.total_return_pct * 100, 2),
                    "sharpe_ratio": round(result.sharpe_ratio, 4),
                    "max_drawdown": round(result.max_drawdown * 100, 2),
                    "total_trades": result.total_trades,
                    "win_rate": metrics["win_rate"],
                    "risk_reward_ratio": metrics["risk_reward_ratio"],
                    "avg_r_multiple": metrics["avg_r_multiple"],
                    "profit_factor": round(result.profit_factor, 4),
                }
                results.append(row)

            except Exception as e:
                logger.warning("Grid search failed for params %s: %s", params, e)

            if idx % 10 == 0 or idx == total:
                logger.info("Grid search progress: %d/%d", idx, total)

        df = pd.DataFrame(results)
        if not df.empty:
            df.sort_values("sharpe_ratio", ascending=False, inplace=True)
            df.reset_index(drop=True, inplace=True)

        return df

    def best_params(
        self,
        data: pd.DataFrame,
        symbol: str = "",
        metric: str = "sharpe_ratio",
    ) -> dict:
        df = self.run(data, symbol)
        if df.empty:
            return {}
        best_row = df.iloc[0]
        param_keys = set(self._param_grid.keys())
        return {k: v for k, v in best_row.items() if k in param_keys}


@dataclass
class OptimizationResult:
    strategy_name: str
    method: str
    objective: str
    results: list[dict] = field(default_factory=list)
    best_params: dict = field(default_factory=dict)
    best_score: float = 0.0

    def top_n(self, n: int = 10) -> list[dict]:
        return self.results[:n]

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.results)


class StrategyOptimizer:
    VALID_OBJECTIVES = {"annualized_return", "sharpe_ratio", "calmar_ratio"}

    def __init__(
        self,
        strategy_name: str,
        param_grid: dict[str, list],
        initial_capital: float = 100000.0,
        risk_config: Optional[RiskConfig] = None,
        commission_rate: float = 0.0003,
        slippage_pct: float = 0.001,
    ):
        self._strategy_name = strategy_name
        self._param_grid = param_grid
        self._initial_capital = initial_capital
        self._risk_config = risk_config or RiskConfig()
        self._commission_rate = commission_rate
        self._slippage_pct = slippage_pct

    def grid_search(
        self,
        data: pd.DataFrame,
        symbol: str = "",
        objective: str = "sharpe_ratio",
    ) -> OptimizationResult:
        if objective not in self.VALID_OBJECTIVES:
            raise ValueError(f"Invalid objective: {objective}. Valid: {self.VALID_OBJECTIVES}")

        keys = list(self._param_grid.keys())
        values = list(self._param_grid.values())
        combinations = list(product(*values))
        all_results = []

        for idx, combo in enumerate(combinations, 1):
            params = dict(zip(keys, combo))
            row = self._run_backtest(params, data, symbol)
            if row:
                all_results.append(row)
            if idx % 10 == 0:
                logger.info("Grid search progress: %d/%d", idx, len(combinations))

        all_results.sort(key=lambda r: r.get(objective, float("-inf")), reverse=True)
        best = all_results[0] if all_results else {}
        best_params = {k: best[k] for k in self._param_grid if k in best}

        return OptimizationResult(
            strategy_name=self._strategy_name,
            method="grid_search",
            objective=objective,
            results=all_results,
            best_params=best_params,
            best_score=best.get(objective, 0.0),
        )

    def random_search(
        self,
        data: pd.DataFrame,
        symbol: str = "",
        objective: str = "sharpe_ratio",
        n_trials: int = 50,
        seed: Optional[int] = None,
    ) -> OptimizationResult:
        if objective not in self.VALID_OBJECTIVES:
            raise ValueError(f"Invalid objective: {objective}. Valid: {self.VALID_OBJECTIVES}")

        if seed is not None:
            random.seed(seed)

        all_results = []
        for trial in range(n_trials):
            params = {
                key: random.choice(values)
                for key, values in self._param_grid.items()
            }
            row = self._run_backtest(params, data, symbol)
            if row:
                all_results.append(row)
            if (trial + 1) % 10 == 0:
                logger.info("Random search progress: %d/%d", trial + 1, n_trials)

        all_results.sort(key=lambda r: r.get(objective, float("-inf")), reverse=True)
        best = all_results[0] if all_results else {}
        best_params = {k: best[k] for k in self._param_grid if k in best}

        return OptimizationResult(
            strategy_name=self._strategy_name,
            method="random_search",
            objective=objective,
            results=all_results,
            best_params=best_params,
            best_score=best.get(objective, 0.0),
        )

    def _run_backtest(self, params: dict, data: pd.DataFrame, symbol: str) -> Optional[dict]:
        try:
            strategy = create_strategy(self._strategy_name, params)
            engine = BacktestEngine(
                strategy=strategy,
                initial_capital=self._initial_capital,
                risk_config=self._risk_config,
                commission_rate=self._commission_rate,
                slippage_pct=self._slippage_pct,
            )
            result = engine.run(data, symbol)

            calmar_ratio = 0.0
            if result.max_drawdown > 0:
                calmar_ratio = result.annualized_return / result.max_drawdown

            return {
                **params,
                "annualized_return": round(result.annualized_return * 100, 2),
                "sharpe_ratio": round(result.sharpe_ratio, 4),
                "calmar_ratio": round(calmar_ratio, 4),
                "max_drawdown": round(result.max_drawdown * 100, 2),
                "total_trades": result.total_trades,
                "win_rate": round(result.win_rate, 4),
                "profit_factor": round(result.profit_factor, 4),
                "total_return_pct": round(result.total_return_pct * 100, 2),
            }
        except Exception as e:
            logger.warning("Backtest failed for params %s: %s", params, e)
            return None
