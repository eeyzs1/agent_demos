import logging
import multiprocessing
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

from trading_system.backtest.engine import BacktestEngine, BacktestResult
from trading_system.backtest.significance import StrategySignificanceTester

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    mean_equity_curve: list[float]
    equity_curve_lower: list[float]
    equity_curve_upper: list[float]
    final_equity_distribution: dict[str, float]
    prob_of_loss: float
    expected_sharpe: float
    n_paths: int
    confidence_level: float = 0.90

    @property
    def final_equity_median(self) -> float:
        return self.final_equity_distribution.get("P50", 0.0)


@dataclass
class ExtendedBacktestResult(BacktestResult):
    prob_montecarlo: Optional[MonteCarloResult] = None
    significance: Optional[dict] = None
    cost_attribution: Optional[dict] = None


class ProbabilisticBacktestEngine:
    def __init__(
        self,
        engine: BacktestEngine,
        n_paths: int = 500,
        n_jobs: int = 4,
        random_seed: int = 42,
    ):
        self._engine = engine
        self._n_paths = n_paths
        self._n_jobs = n_jobs
        self._rng = np.random.RandomState(random_seed)
        self._significance_tester = StrategySignificanceTester(n_simulations=2000)

    def run_probabilistic_montecarlo(
        self,
        data: "pd.DataFrame",
        symbol: str = "",
        win_probabilities: Optional[list[float]] = None,
        n_trials: int = 1,
    ) -> MonteCarloResult:
        import pandas as pd

        all_equity_curves = []
        all_final_equities = []
        all_sharpes = []

        seeds = self._rng.randint(0, 2**31 - 1, size=self._n_paths)

        for path_i in range(self._n_paths):
            path_rng = np.random.RandomState(seeds[path_i])

            signals = self._engine._strategy.generate_signals(data)
            signal_count = len(signals)

            if win_probabilities is None:
                win_probabilities = [0.5] * max(signal_count, 1)

            executed_signals = []
            for i, sig in enumerate(signals):
                prob = win_probabilities[min(i, len(win_probabilities) - 1)]
                if path_rng.random() < prob:
                    executed_signals.append(sig)

            import copy
            temp_engine = copy.deepcopy(self._engine)

            original_generate = temp_engine._strategy.generate_signals
            temp_engine._strategy.generate_signals = lambda d, sigs=executed_signals: sigs

            result = temp_engine.run(data, symbol)
            temp_engine._strategy.generate_signals = original_generate

            all_equity_curves.append(list(result.equity_curve))
            all_final_equities.append(result.equity_curve[-1] if result.equity_curve else 0)
            all_sharpes.append(result.sharpe_ratio)

        max_len = max(len(ec) for ec in all_equity_curves)
        padded_curves = np.array([
            ec + [ec[-1]] * (max_len - len(ec)) for ec in all_equity_curves
        ])

        mean_curve = np.mean(padded_curves, axis=0)
        alpha = (1 - 0.90) / 2
        lower_curve = np.percentile(padded_curves, alpha * 100, axis=0)
        upper_curve = np.percentile(padded_curves, (1 - alpha) * 100, axis=0)

        final_equities = np.array(all_final_equities)
        prob_of_loss = float(np.mean(final_equities < self._engine._initial_capital))

        mc_result = MonteCarloResult(
            mean_equity_curve=[round(float(v), 2) for v in mean_curve],
            equity_curve_lower=[round(float(v), 2) for v in lower_curve],
            equity_curve_upper=[round(float(v), 2) for v in upper_curve],
            final_equity_distribution={
                "P10": round(float(np.percentile(final_equities, 10)), 2),
                "P25": round(float(np.percentile(final_equities, 25)), 2),
                "P50": round(float(np.percentile(final_equities, 50)), 2),
                "P75": round(float(np.percentile(final_equities, 75)), 2),
                "P90": round(float(np.percentile(final_equities, 90)), 2),
            },
            prob_of_loss=round(prob_of_loss, 4),
            expected_sharpe=round(float(np.mean(all_sharpes)), 4),
            n_paths=self._n_paths,
        )

        logger.info(
            "Monte Carlo backtest: %d paths, median_final=%.2f, P(loss)=%.2f%%, expected_sharpe=%.2f",
            self._n_paths, mc_result.final_equity_median, prob_of_loss * 100, mc_result.expected_sharpe,
        )

        return mc_result

    def run_with_significance(
        self,
        data: "pd.DataFrame",
        symbol: str = "",
        n_trials: int = 1,
        win_probabilities: Optional[list[float]] = None,
    ) -> dict:
        result = self._engine.run(data, symbol)

        returns = pd.Series(result.equity_curve).pct_change().dropna()
        sig_report = self._significance_tester.test(
            strategy_returns=returns.values,
            n_trials=n_trials,
        )

        mc_result = self.run_probabilistic_montecarlo(
            data, symbol, win_probabilities, n_trials,
        )

        return {
            "backtest": result,
            "significance": {
                "sharpe_ratio": sig_report.sharpe_ratio,
                "deflated_sharpe": sig_report.deflated_sharpe,
                "haircut_sharpe": sig_report.haircut_sharpe,
                "significance_level": sig_report.significance_level,
            },
            "monte_carlo": {
                "median_final_equity": mc_result.final_equity_median,
                "prob_of_loss_pct": round(mc_result.prob_of_loss * 100, 2),
                "expected_sharpe": mc_result.expected_sharpe,
                "equity_distribution": mc_result.final_equity_distribution,
            },
        }
