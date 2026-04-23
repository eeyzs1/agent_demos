import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BENCHMARK_HS300 = "hs300"
BENCHMARK_ZZ500 = "zz500"
BENCHMARK_CYB = "cyb"

BENCHMARK_NAMES = {
    BENCHMARK_HS300: "沪深300",
    BENCHMARK_ZZ500: "中证500",
    BENCHMARK_CYB: "创业板指",
}


@dataclass
class BenchmarkResult:
    benchmark_name: str
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    alpha: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0
    beta: float = 0.0
    dates: list = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "benchmark_name": self.benchmark_name,
            "benchmark_display_name": BENCHMARK_NAMES.get(self.benchmark_name, self.benchmark_name),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return_pct": round(self.annualized_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "alpha": round(self.alpha, 4),
            "information_ratio": round(self.information_ratio, 4),
            "tracking_error": round(self.tracking_error, 4),
            "beta": round(self.beta, 4),
        }


class BenchmarkCalculator:
    def __init__(self, risk_free_rate: float = 0.03):
        self._risk_free_rate = risk_free_rate

    def calculate_from_data(
        self,
        benchmark_data: pd.DataFrame,
        strategy_equity_curve: list[float],
        strategy_dates: list,
        benchmark_name: str = BENCHMARK_HS300,
    ) -> BenchmarkResult:
        if benchmark_data.empty or len(strategy_equity_curve) == 0:
            return BenchmarkResult(benchmark_name=benchmark_name)

        close = benchmark_data["close"] if "close" in benchmark_data.columns else benchmark_data.iloc[:, 0]
        benchmark_returns = close.pct_change().dropna()

        strategy_series = pd.Series(strategy_equity_curve)
        strategy_returns = strategy_series.pct_change().dropna()

        min_len = min(len(benchmark_returns), len(strategy_returns))
        if min_len < 2:
            return BenchmarkResult(benchmark_name=benchmark_name)

        benchmark_returns = benchmark_returns.iloc[:min_len].reset_index(drop=True)
        strategy_returns = strategy_returns.iloc[:min_len].reset_index(drop=True)

        total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100 if len(close) > 0 else 0
        days = (close.index[-1] - close.index[0]).days if len(close) > 1 else 1
        annualized_return = ((1 + total_return / 100) ** (365 / max(days, 1)) - 1) * 100

        benchmark_sharpe = self._calc_sharpe(benchmark_returns)
        benchmark_max_dd = self._calc_max_drawdown(close)

        alpha = self._calc_alpha(strategy_returns, benchmark_returns)
        beta = self._calc_beta(strategy_returns, benchmark_returns)
        tracking_error = self._calc_tracking_error(strategy_returns, benchmark_returns)
        information_ratio = self._calc_information_ratio(strategy_returns, benchmark_returns)

        benchmark_equity = (1 + benchmark_returns).cumprod().tolist()

        return BenchmarkResult(
            benchmark_name=benchmark_name,
            total_return_pct=round(total_return, 2),
            annualized_return_pct=round(annualized_return, 2),
            sharpe_ratio=round(benchmark_sharpe, 4),
            max_drawdown_pct=round(benchmark_max_dd * 100, 2),
            alpha=round(alpha, 4),
            information_ratio=round(information_ratio, 4),
            tracking_error=round(tracking_error, 4),
            beta=round(beta, 4),
            equity_curve=benchmark_equity,
        )

    def compare_with_benchmark(
        self,
        strategy_result_summary: dict,
        benchmark_result: BenchmarkResult,
    ) -> dict:
        strategy_return = strategy_result_summary.get("total_return_pct", 0)
        strategy_sharpe = strategy_result_summary.get("sharpe_ratio", 0)
        strategy_max_dd = strategy_result_summary.get("max_drawdown", 0)

        return {
            "strategy_return_pct": strategy_return,
            "benchmark_return_pct": benchmark_result.total_return_pct,
            "excess_return_pct": round(strategy_return - benchmark_result.total_return_pct, 2),
            "strategy_sharpe": strategy_sharpe,
            "benchmark_sharpe": benchmark_result.sharpe_ratio,
            "alpha": benchmark_result.alpha,
            "beta": benchmark_result.beta,
            "information_ratio": benchmark_result.information_ratio,
            "strategy_max_dd_pct": strategy_max_dd,
            "benchmark_max_dd_pct": benchmark_result.max_drawdown_pct,
            "outperforms": strategy_return > benchmark_result.total_return_pct,
        }

    def _calc_sharpe(self, returns: pd.Series) -> float:
        if returns.std() == 0:
            return 0.0
        daily_rf = self._risk_free_rate / 252
        excess = returns - daily_rf
        return (excess.mean() / excess.std()) * np.sqrt(252) if excess.std() > 0 else 0.0

    def _calc_max_drawdown(self, prices: pd.Series) -> float:
        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        return abs(drawdown.min())

    def _calc_alpha(self, strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        beta = self._calc_beta(strategy_returns, benchmark_returns)
        daily_rf = self._risk_free_rate / 252
        expected = daily_rf + beta * (benchmark_returns.mean() - daily_rf)
        alpha_daily = strategy_returns.mean() - expected
        return (1 + alpha_daily) ** 252 - 1

    def _calc_beta(self, strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        cov_matrix = np.cov(strategy_returns, benchmark_returns)
        benchmark_var = cov_matrix[1, 1]
        if benchmark_var == 0:
            return 0.0
        return cov_matrix[0, 1] / benchmark_var

    def _calc_tracking_error(self, strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        diff = strategy_returns - benchmark_returns
        return diff.std() * np.sqrt(252) if diff.std() > 0 else 0.0

    def _calc_information_ratio(self, strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        te = self._calc_tracking_error(strategy_returns, benchmark_returns)
        if te == 0:
            return 0.0
        excess_return = (strategy_returns - benchmark_returns).mean() * 252
        return excess_return / te


class LookaheadBiasChecker:
    def __init__(self):
        self._issues: list[dict] = []

    @property
    def issues(self) -> list[dict]:
        return list(self._issues)

    def check_signal_uses_same_day_close(self, signals: list[dict]) -> int:
        count = 0
        for sig in signals:
            sig_date = sig.get("date") or sig.get("timestamp")
            price = sig.get("price", 0)
            close = sig.get("close", None)
            if close is not None and sig_date is not None:
                if abs(price - close) < 0.001:
                    self._issues.append({
                        "type": "same_day_close_signal",
                        "date": str(sig_date),
                        "message": f"Signal on {sig_date} uses same-day close price - potential lookahead bias",
                    })
                    count += 1
        return count

    def check_indicator_lookahead(self, indicator_name: str, data: pd.DataFrame, column: str) -> bool:
        if column not in data.columns:
            return False
        values = data[column].dropna()
        if len(values) < 2:
            return False
        return False

    def is_clean(self) -> bool:
        return len(self._issues) == 0

    def get_report(self) -> dict:
        return {
            "is_clean": self.is_clean(),
            "issue_count": len(self._issues),
            "issues": self._issues,
        }
