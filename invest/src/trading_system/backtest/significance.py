import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SignificanceReport:
    sharpe_ratio: float
    deflated_sharpe: float
    haircut_sharpe: float
    monthly_alpha_t_stat: float
    significance_level: str
    n_trials: int
    n_simulations: int

    @property
    def is_significant(self) -> bool:
        return self.significance_level in ("SIGNIFICANT", "HIGHLY_SIGNIFICANT")


class StrategySignificanceTester:
    def __init__(self, n_simulations: int = 2000, random_seed: int = 42):
        self._n_simulations = n_simulations
        self._rng = np.random.RandomState(random_seed)

    def test(
        self,
        strategy_returns: np.ndarray,
        benchmark_returns: Optional[np.ndarray] = None,
        n_trials: int = 1,
        trading_days: int = 252,
    ) -> SignificanceReport:
        if len(strategy_returns) < 20:
            logger.warning("Insufficient returns data for significance testing")
            return SignificanceReport(
                sharpe_ratio=0.0, deflated_sharpe=0.0, haircut_sharpe=0.0,
                monthly_alpha_t_stat=0.0, significance_level="NOT SIGNIFICANT",
                n_trials=n_trials, n_simulations=0,
            )

        excess_returns = strategy_returns
        if benchmark_returns is not None and len(benchmark_returns) == len(strategy_returns):
            excess_returns = strategy_returns - benchmark_returns

        sr = self._calc_sharpe(excess_returns, trading_days)
        dsr = self._calc_deflated_sharpe(excess_returns, n_trials, trading_days)

        hsr = self._calc_haircut_sharpe(sr, n_trials, len(excess_returns))

        monthly_returns = self._to_monthly(excess_returns)
        if len(monthly_returns) >= 3:
            from scipy import stats
            t_stat, _ = stats.ttest_1samp(monthly_returns, 0)
            monthly_alpha_t_stat = float(t_stat)
        else:
            monthly_alpha_t_stat = 0.0

        if dsr > 3.0:
            significance_level = "HIGHLY SIGNIFICANT"
        elif dsr > 2.0:
            significance_level = "SIGNIFICANT"
        elif dsr > 1.5:
            significance_level = "WEAK"
        else:
            significance_level = "NOT SIGNIFICANT"

        logger.info(
            "Significance test: SR=%.4f DSR=%.4f HSR=%.4f level=%s trials=%d",
            sr, dsr, hsr, significance_level, n_trials,
        )

        return SignificanceReport(
            sharpe_ratio=round(sr, 4),
            deflated_sharpe=round(dsr, 4),
            haircut_sharpe=round(hsr, 4),
            monthly_alpha_t_stat=round(monthly_alpha_t_stat, 4),
            significance_level=significance_level,
            n_trials=n_trials,
            n_simulations=self._n_simulations,
        )

    def _calc_deflated_sharpe(
        self,
        returns: np.ndarray,
        n_trials: int,
        trading_days: int,
    ) -> float:
        if n_trials <= 1:
            return self._calc_sharpe(returns, trading_days)

        T = len(returns)

        null_sharpes = np.zeros(self._n_simulations)
        for i in range(self._n_simulations):
            max_sr = -np.inf
            for _ in range(n_trials):
                random_returns = self._rng.randn(T) * np.std(returns)
                sr_trial = self._calc_sharpe(random_returns, trading_days)
                if sr_trial > max_sr:
                    max_sr = sr_trial
            null_sharpes[i] = max_sr

        e_max_sr = float(np.mean(null_sharpes))
        std_max_sr = float(np.std(null_sharpes))

        observed_sr = self._calc_sharpe(returns, trading_days)

        if std_max_sr > 0:
            dsr = (observed_sr - e_max_sr) / std_max_sr
        else:
            dsr = 0.0

        return dsr

    def _calc_haircut_sharpe(
        self,
        sr: float,
        n_trials: int,
        sample_size: int,
    ) -> float:
        if n_trials <= 1 or sample_size <= 0:
            return sr

        correction_factor = np.sqrt(np.log(n_trials) / sample_size)
        correction_factor = min(correction_factor, 1.0)

        hsr = sr * (1 - correction_factor)
        return hsr

    @staticmethod
    def _calc_sharpe(returns: np.ndarray, trading_days: int) -> float:
        if len(returns) < 2:
            return 0.0
        mu = np.mean(returns)
        sigma = np.std(returns, ddof=1)
        if sigma <= 0:
            return 0.0
        return float(mu / sigma * np.sqrt(trading_days))

    @staticmethod
    def _to_monthly(returns: np.ndarray) -> np.ndarray:
        monthly = []
        chunk_size = 21
        for i in range(0, len(returns), chunk_size):
            chunk = returns[i:i + chunk_size]
            monthly.append(np.sum(chunk))
        return np.array(monthly)
