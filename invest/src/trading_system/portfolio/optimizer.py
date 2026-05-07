import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class PortfolioAllocation:
    weights: dict[str, float]
    expected_portfolio_return: float
    expected_portfolio_volatility: float
    sharpe_ratio: float
    diversification_ratio: float
    method: str

    @property
    def weights_array(self) -> np.ndarray:
        return np.array(list(self.weights.values()))

    @property
    def symbols(self) -> list[str]:
        return list(self.weights.keys())


class PortfolioOptimizer:
    def __init__(
        self,
        max_exposure: float = 0.95,
        max_single: float = 0.25,
        max_turnover: float = 0.30,
        lambda_aversion: Optional[float] = None,
        target_sharpe: float = 1.0,
        target_vol: float = 0.15,
    ):
        self._max_exposure = max_exposure
        self._max_single = max_single
        self._max_turnover = max_turnover
        self._lambda = lambda_aversion or (target_sharpe / target_vol)

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance_matrix: pd.DataFrame,
        current_weights: Optional[dict[str, float]] = None,
    ) -> PortfolioAllocation:
        symbols = list(expected_returns.keys())
        for s in symbols:
            if s not in covariance_matrix.index:
                raise ValueError(f"Symbol {s} not found in covariance matrix")

        cov_subset = covariance_matrix.loc[symbols, symbols]
        cov_values = cov_subset.values
        mu = np.array([expected_returns[s] for s in symbols])
        N = len(symbols)

        w_prev = np.zeros(N)
        if current_weights:
            for i, s in enumerate(symbols):
                w_prev[i] = current_weights.get(s, 0.0)

        w0 = np.ones(N) / N

        def objective(w):
            return 0.5 * w @ cov_values @ w - self._lambda * mu @ w

        constraints = [
            {"type": "ineq", "fun": lambda w: self._max_exposure - np.sum(w)},
            {"type": "ineq", "fun": lambda w: np.sum(w)},
        ]

        bounds = [(0.0, self._max_single) for _ in range(N)]

        if self._max_turnover > 0 and current_weights is not None:
            constraints.append({
                "type": "ineq",
                "fun": lambda w: self._max_turnover - np.sum(np.abs(w - w_prev)),
            })

        result = minimize(
            objective, w0, method="SLSQP", bounds=bounds,
            constraints=constraints, options={"maxiter": 1000, "ftol": 1e-10},
        )

        if not result.success:
            logger.warning("Optimization did not converge: %s. Using equal weights.", result.message)
            w_opt = w0
        else:
            w_opt = result.x
            w_opt = np.maximum(w_opt, 0)
            w_sum = w_opt.sum()
            if w_sum > 0:
                w_opt = w_opt / w_sum * min(w_sum, self._max_exposure)

        weights = {s: round(float(w_opt[i]), 6) for i, s in enumerate(symbols)}

        port_return = float(mu @ w_opt)
        port_vol = float(np.sqrt(w_opt @ cov_values @ w_opt))
        sharpe = float(port_return / port_vol) if port_vol > 0 else 0.0
        div_ratio = float(1.0 / np.sum(w_opt ** 2)) if np.sum(w_opt ** 2) > 0 else 0.0

        logger.info(
            "Markowitz optimization: symbols=%d return=%.4f vol=%.4f sharpe=%.4f div=%.2f",
            N, port_return, port_vol, sharpe, div_ratio,
        )

        return PortfolioAllocation(
            weights=weights,
            expected_portfolio_return=round(port_return, 6),
            expected_portfolio_volatility=round(port_vol, 6),
            sharpe_ratio=round(sharpe, 4),
            diversification_ratio=round(div_ratio, 2),
            method="markowitz",
        )

    def optimize_black_litterman(
        self,
        covariance_matrix: pd.DataFrame,
        symbols: list[str],
        market_caps: Optional[dict[str, float]] = None,
        risk_aversion: Optional[float] = None,
    ) -> PortfolioAllocation:
        N = len(symbols)
        if market_caps:
            total_cap = sum(market_caps.values())
            equilibrium_weights = {
                s: market_caps.get(s, 1.0 / N) / total_cap for s in symbols
            }
        else:
            equilibrium_weights = {s: 1.0 / N for s in symbols}

        w_eq = np.array([equilibrium_weights[s] for s in symbols])
        cov_values = covariance_matrix.loc[symbols, symbols].values
        lambda_bl = risk_aversion or self._lambda

        equilibrium_returns = lambda_bl * cov_values @ w_eq
        expected_returns = {s: float(equilibrium_returns[i]) for i, s in enumerate(symbols)}

        return self.optimize(expected_returns, covariance_matrix)
