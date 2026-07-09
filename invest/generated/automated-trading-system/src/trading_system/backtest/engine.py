"""Backtest Engine — 7 key metrics, Monte Carlo simulation, Deflated Sharpe Ratio.

Produces:
- 7 key metrics: win_rate, risk_reward_ratio, max_drawdown, risk_per_trade,
  annual_return, max_consecutive_losses, avg_r_multiple (AC3)
- Monte Carlo backtest: P10/P25/P50/P75/P90 equity distribution, loss probability (AC4)
- Deflated Sharpe Ratio with multiple testing penalty (AC8)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.event_bus import get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """A single trade record."""
    entry_date: str
    exit_date: str
    symbol: str
    entry_price: float
    exit_price: float
    quantity: int = 100
    direction: str = "long"
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0

    def __post_init__(self):
        if self.direction == "long":
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - self.exit_price) * self.quantity
        if self.entry_price > 0:
            self.pnl_pct = (self.exit_price / self.entry_price - 1) * 100


@dataclass
class BacktestMetrics:
    """The 7 key backtest metrics (AC3)."""
    win_rate: float = 0.0
    risk_reward_ratio: float = 0.0
    max_drawdown: float = 0.0
    risk_per_trade: float = 0.0
    annual_return: float = 0.0
    max_consecutive_losses: int = 0
    avg_r_multiple: float = 0.0

    # Additional metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation results (AC4)."""
    percentiles: Dict[str, float] = field(default_factory=dict)
    loss_probability: float = 0.0
    mean_equity: float = 0.0
    std_equity: float = 0.0
    equity_curves: List[np.ndarray] = field(default_factory=list)
    simulations: int = 0


class BacktestEngine:
    """Backtest engine with 7 key metrics, Monte Carlo, and Deflated Sharpe Ratio.

    Depends on strategy and data layers, must not import risk or execution (AR005).
    """

    def __init__(self, config_dir: str = "config"):
        config = get_config(config_dir)
        self._config = config
        self._audit = get_audit_logger()
        self._event_bus = get_event_bus()

        # Config
        self._commission_rate = config.get("backtest.commission_rate", 0.0003)
        self._slippage = config.get("backtest.slippage", 0.001)
        self._risk_free_rate = 0.03  # 3% annual risk-free rate

        # Results
        self._trades: List[Trade] = []
        self._equity_curve: pd.Series = None
        self._metrics: BacktestMetrics = None
        self._monte_carlo: MonteCarloResult = None

    # --- AC3: 7 Key Metrics ---

    def run_backtest(
        self,
        price_data: pd.DataFrame,
        signals: pd.DataFrame,
        initial_capital: float = 100000.0,
        position_size_pct: float = 0.02,
        commission_rate: float = None,
        slippage: float = None,
    ) -> Tuple[BacktestMetrics, List[Trade]]:
        """Run a backtest on price data with signals.

        Args:
            price_data: DataFrame with columns: date, open, high, low, close, volume.
            signals: DataFrame with columns: date, signal (1=buy, -1=sell, 0=hold).
            initial_capital: Starting capital.
            position_size_pct: Percentage of capital per trade.
            commission_rate: Commission rate (default from config).
            slippage: Slippage (default from config).

        Returns:
            (BacktestMetrics, list of Trade objects)
        """
        commission = commission_rate if commission_rate is not None else self._commission_rate
        slip = slippage if slippage is not None else self._slippage

        self._trades = []
        capital = initial_capital
        peak_capital = initial_capital

        # Ensure date columns
        if "date" in price_data.columns:
            price_data = price_data.set_index("date")
        if "date" in signals.columns:
            signals = signals.set_index("date")

        # Align indices
        common_idx = price_data.index.intersection(signals.index)
        price_data = price_data.loc[common_idx]
        signals = signals.loc[common_idx]

        position = 0
        entry_price = 0.0
        entry_date = None
        equity = [initial_capital]
        equity_dates = [price_data.index[0] if len(price_data) > 0 else None]

        for i, (idx, row) in enumerate(price_data.iterrows()):
            close = row.get("close", 0)
            signal_val = signals.loc[idx, "signal"] if idx in signals.index else 0

            if signal_val == 1 and position == 0:
                # Buy signal
                entry_price = close * (1 + slip)
                position = int(capital * position_size_pct / entry_price)
                entry_date = str(idx)
                commission_cost = entry_price * position * commission
                capital -= commission_cost

            elif signal_val == -1 and position > 0:
                # Sell signal
                exit_price = close * (1 - slip)
                commission_cost = exit_price * position * commission
                trade_pnl = (exit_price - entry_price) * position - commission_cost

                capital += exit_price * position - commission_cost
                if capital > peak_capital:
                    peak_capital = capital

                # Calculate holding days from the entry index position
                h_days = 0
                if entry_date is not None:
                    try:
                        entry_idx = equity_dates.index(entry_date)
                        h_days = i - entry_idx
                    except ValueError:
                        h_days = 0

                trade = Trade(
                    entry_date=str(entry_date),
                    exit_date=str(idx),
                    symbol="",
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=position,
                    pnl=trade_pnl,
                    holding_days=h_days,
                )
                self._trades.append(trade)
                position = 0
                entry_price = 0.0
                entry_date = None

            equity.append(capital)
            equity_dates.append(idx)

        # Close any open position at end
        if position > 0:
            last_close = price_data.iloc[-1]["close"]
            exit_price = last_close * (1 - slip)
            commission_cost = exit_price * position * commission
            trade_pnl = (exit_price - entry_price) * position - commission_cost
            capital += exit_price * position - commission_cost

            trade = Trade(
                entry_date=str(entry_date),
                exit_date=str(price_data.index[-1]),
                symbol="",
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=position,
                pnl=trade_pnl,
            )
            self._trades.append(trade)

        self._equity_curve = pd.Series(equity, index=equity_dates[:len(equity)])
        self._metrics = self._calculate_metrics(initial_capital, peak_capital)

        self._audit.log(
            "backtest_results",
            check_id="backtest_run",
            result="OK",
            payload={
                "total_trades": self._metrics.total_trades,
                "win_rate": self._metrics.win_rate,
                "sharpe_ratio": self._metrics.sharpe_ratio,
            },
        )
        self._event_bus.publish(
            "backtest.complete",
            {"metrics": self._metrics.__dict__, "trades": len(self._trades)},
        )

        return self._metrics, self._trades

    def _calculate_metrics(
        self, initial_capital: float, peak_capital: float
    ) -> BacktestMetrics:
        """Calculate the 7 key metrics from trade history."""
        if not self._trades:
            return BacktestMetrics()

        trades = self._trades
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]

        m = BacktestMetrics()
        m.total_trades = len(trades)
        m.winning_trades = len(winning)
        m.losing_trades = len(losing)

        # 1. Win rate
        m.win_rate = m.winning_trades / m.total_trades if m.total_trades > 0 else 0.0

        # 2. Risk/Reward ratio
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0.0
        avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 0.0
        m.risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        # 3. Max drawdown
        if self._equity_curve is not None:
            rolling_max = self._equity_curve.cummax()
            drawdowns = (self._equity_curve - rolling_max) / rolling_max
            m.max_drawdown = abs(drawdowns.min()) if not drawdowns.empty else 0.0
        else:
            m.max_drawdown = (peak_capital - self._equity_curve.iloc[-1]) / peak_capital if peak_capital > 0 else 0.0

        # 4. Risk per trade (average % of capital at risk)
        m.risk_per_trade = np.mean([abs(t.pnl_pct) for t in trades]) if trades else 0.0

        # 5. Annual return
        total_return = (self._equity_curve.iloc[-1] / initial_capital - 1) if self._equity_curve is not None and initial_capital > 0 else 0.0
        if self._equity_curve is not None and len(self._equity_curve) > 1:
            try:
                days = (pd.to_datetime(self._equity_curve.index[-1]) - pd.to_datetime(self._equity_curve.index[0])).days
                years = max(days / 365.25, 0.01)
                m.annual_return = (1 + total_return) ** (1 / years) - 1
            except Exception:
                m.annual_return = total_return

        # 6. Max consecutive losses
        max_consec = 0
        current_consec = 0
        for t in trades:
            if t.pnl <= 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0
        m.max_consecutive_losses = max_consec

        # 7. Average R-multiple
        r_values = [t.pnl / (abs(t.pnl_pct) * initial_capital / 100) if t.pnl_pct != 0 else 0 for t in trades]
        m.avg_r_multiple = np.mean(r_values) if r_values else 0.0

        # Additional metrics
        m.total_pnl = sum(t.pnl for t in trades)
        m.profit_factor = (
            sum(t.pnl for t in winning) / abs(sum(t.pnl for t in losing))
            if losing and sum(t.pnl for t in losing) != 0 else 0.0
        )

        # Sharpe ratio
        if self._equity_curve is not None and len(self._equity_curve) > 1:
            daily_returns = self._equity_curve.pct_change().dropna()
            if len(daily_returns) > 1 and daily_returns.std() > 0:
                excess = daily_returns.mean() - self._risk_free_rate / 252
                m.sharpe_ratio = excess / daily_returns.std() * np.sqrt(252)
                # Sortino ratio (downside deviation only)
                downside = daily_returns[daily_returns < 0]
                downside_std = downside.std() if len(downside) > 1 else daily_returns.std()
                m.sortino_ratio = excess / downside_std * np.sqrt(252) if downside_std > 0 else 0.0
                # Calmar ratio
                m.calmar_ratio = m.annual_return / m.max_drawdown if m.max_drawdown > 0 else 0.0

        return m

    # --- AC4: Monte Carlo Simulation ---

    def run_monte_carlo(
        self,
        num_simulations: int = None,
        confidence_levels: List[float] = None,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation on trade history.

        Args:
            num_simulations: Number of simulations (default from config).
            confidence_levels: Percentile levels (default from config).

        Returns:
            MonteCarloResult with equity distribution and loss probability.
        """
        sims = num_simulations or self._config.get("monte_carlo.simulations", 1000)
        levels = confidence_levels or self._config.get("monte_carlo.confidence_levels", [0.10, 0.25, 0.50, 0.75, 0.90])

        if not self._trades:
            logger.warning("No trades available for Monte Carlo simulation")
            return MonteCarloResult(simulations=sims)

        trade_returns = np.array([t.pnl_pct for t in self._trades])
        n_trades = len(trade_returns)
        equity_curves = []
        final_equities = []

        rng = np.random.RandomState(42)
        for _ in range(sims):
            # Randomly sample trade returns with replacement
            sampled = rng.choice(trade_returns, size=n_trades, replace=True)
            equity = 100.0  # Start at 100
            curve = [equity]
            for ret in sampled:
                equity *= (1 + ret / 100)
                curve.append(equity)
            equity_curves.append(np.array(curve))
            final_equities.append(equity)

        final_equities = np.array(final_equities)
        percentiles = {}
        for level in levels:
            percentiles[f"P{int(level*100)}"] = float(np.percentile(final_equities, level * 100))

        loss_probability = float(np.mean(final_equities < 100.0))

        result = MonteCarloResult(
            percentiles=percentiles,
            loss_probability=loss_probability,
            mean_equity=float(np.mean(final_equities)),
            std_equity=float(np.std(final_equities)),
            equity_curves=equity_curves,
            simulations=sims,
        )

        self._monte_carlo = result
        self._audit.log(
            "backtest_results",
            check_id="monte_carlo",
            result="OK",
            payload={
                "simulations": sims,
                "loss_probability": loss_probability,
                "percentiles": percentiles,
            },
        )
        self._event_bus.publish("backtest.monte_carlo_complete", percentiles)

        return result

    # --- AC8: Deflated Sharpe Ratio ---

    def calculate_deflated_sharpe(
        self,
        num_trials: int = None,
        variance_multiplier: float = None,
    ) -> Dict[str, Any]:
        """Calculate the Deflated Sharpe Ratio (DSR) with multiple testing penalty.

        The DSR penalizes the Sharpe ratio for the number of strategies tested,
        addressing the multiple testing problem in strategy selection.

        Haircut Sharpe = (SR - E[max(SR)]) / Std[max(SR)]

        Args:
            num_trials: Number of independent trials tested (default from config).
            variance_multiplier: Variance multiplier for E[max] (default from config).

        Returns:
            Dict with sharpe_ratio, haircut_sharpe, deflated_sharpe, p_value, is_significant.
        """
        trials = num_trials or self._config.get("deflated_sharpe.num_trials", 100)
        var_mult = variance_multiplier or self._config.get("deflated_sharpe.variance_multiplier", 3.0)

        if self._metrics is None or self._metrics.sharpe_ratio == 0:
            return {
                "sharpe_ratio": 0.0,
                "haircut_sharpe": 0.0,
                "deflated_sharpe": 0.0,
                "p_value": 1.0,
                "is_significant": False,
                "num_trials": trials,
            }

        sr = self._metrics.sharpe_ratio
        # Expected maximum SR under null (no skill)
        # Using the approximation: E[max(SR)] ≈ sqrt(2*log(N)) * sqrt(var)
        # where N = num_trials
        expected_max = np.sqrt(2 * np.log(max(trials, 1))) * var_mult ** 0.5

        # Haircut Sharpe
        haircut = max(0, sr - expected_max)

        # Deflated Sharpe Ratio (probability that SR is genuine)
        # Using the asymptotic distribution
        dsr = sr / np.sqrt(var_mult) if var_mult > 0 else 0.0

        # Approximate p-value using normal distribution
        # H0: true SR = 0, under multiple testing
        p_value = 1.0 - self._normal_cdf(sr / np.sqrt(var_mult / 252))
        # Adjust p-value for multiple testing (Bonferroni)
        adjusted_p = min(p_value * trials, 1.0)

        is_significant = adjusted_p < 0.05

        result = {
            "sharpe_ratio": round(sr, 4),
            "haircut_sharpe": round(haircut, 4),
            "deflated_sharpe": round(dsr, 4),
            "expected_max_sr": round(expected_max, 4),
            "p_value": round(p_value, 4),
            "adjusted_p_value": round(adjusted_p, 4),
            "is_significant": is_significant,
            "num_trials": trials,
            "variance_multiplier": var_mult,
        }

        self._audit.log(
            "backtest_results",
            check_id="deflated_sharpe",
            result="OK",
            payload=result,
        )
        self._event_bus.publish("backtest.dsr_complete", result)

        return result

    def _normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF."""
        # Using the Abramowitz and Stegun approximation
        a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x) / np.sqrt(2)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * np.exp(-x * x)
        return 0.5 * (1.0 + sign * y)

    # --- Utility ---

    def get_metrics(self) -> Optional[BacktestMetrics]:
        """Get the latest backtest metrics."""
        return self._metrics

    def get_trades(self) -> List[Trade]:
        """Get all trades from the last backtest."""
        return self._trades

    def get_equity_curve(self) -> Optional[pd.Series]:
        """Get the equity curve from the last backtest."""
        return self._equity_curve

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive backtest summary."""
        if self._metrics is None:
            return {"status": "no_backtest_run"}

        summary = {
            "metrics": self._metrics.__dict__,
            "total_trades": len(self._trades),
            "monte_carlo": (
                {
                    "percentiles": self._monte_carlo.percentiles,
                    "loss_probability": self._monte_carlo.loss_probability,
                }
                if self._monte_carlo else None
            ),
        }
        return summary