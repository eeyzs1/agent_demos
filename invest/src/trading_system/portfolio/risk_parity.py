import logging

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.optimize import minimize

from trading_system.portfolio.optimizer import PortfolioAllocation

logger = logging.getLogger(__name__)


class RiskParityOptimizer:
    def __init__(self, tol: float = 1e-8, max_iter: int = 10000):
        self._tol = tol
        self._max_iter = max_iter

    def optimize(self, covariance_matrix: pd.DataFrame) -> PortfolioAllocation:
        symbols = list(covariance_matrix.index)
        cov = covariance_matrix.values
        N = len(symbols)

        w0 = np.ones(N) / N

        def risk_contributions(w):
            sigma_p = np.sqrt(w @ cov @ w)
            if sigma_p <= 0:
                return np.ones(N) / N
            mrc = cov @ w
            rc = w * mrc / sigma_p
            return rc

        def objective(w):
            rc = risk_contributions(w)
            target = 1.0 / N
            return np.sum((rc - target) ** 2)

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        ]
        bounds = [(0.0, 1.0) for _ in range(N)]

        result = minimize(
            objective, w0, method="SLSQP", bounds=bounds,
            constraints=constraints,
            options={"maxiter": self._max_iter, "ftol": self._tol},
        )

        if not result.success:
            logger.warning("Risk parity did not converge: %s", result.message)

        w_opt = result.x
        w_opt = np.maximum(w_opt, 0)
        w_opt = w_opt / w_opt.sum()

        weights = {s: round(float(w_opt[i]), 6) for i, s in enumerate(symbols)}

        sigma_p = float(np.sqrt(w_opt @ cov @ w_opt))
        port_return = 0.0
        sharpe = 0.0
        div_ratio = float(1.0 / np.sum(w_opt ** 2)) if np.sum(w_opt ** 2) > 0 else 0.0

        rc = risk_contributions(w_opt)
        rc_dict = {s: round(float(rc[i]), 6) for i, s in enumerate(symbols)}

        logger.info(
            "Risk Parity: symbols=%d vol=%.4f div=%.2f max_rc_diff=%.4f",
            N, sigma_p, div_ratio, float(np.max(np.abs(rc - 1.0 / N))),
        )

        allocation = PortfolioAllocation(
            weights=weights,
            expected_portfolio_return=round(port_return, 6),
            expected_portfolio_volatility=round(sigma_p, 6),
            sharpe_ratio=round(sharpe, 4),
            diversification_ratio=round(div_ratio, 2),
            method="risk_parity",
        )
        allocation.__dict__["risk_contributions"] = rc_dict
        return allocation


class HRPOptimizer:
    def optimize(self, covariance_matrix: pd.DataFrame) -> PortfolioAllocation:
        symbols = list(covariance_matrix.index)
        cov = covariance_matrix.values
        N = len(symbols)

        corr = covariance_matrix.corr().values
        dist_matrix = np.sqrt(0.5 * (1 - corr))
        np.fill_diagonal(dist_matrix, 0)

        condensed_dist = squareform(dist_matrix)
        linkage_matrix = linkage(condensed_dist, method="ward")

        clusters = fcluster(linkage_matrix, t=2, criterion="maxclust")

        sorted_indices = self._quasi_diag(linkage_matrix, N)
        sorted_symbols = [symbols[i] for i in sorted_indices]

        w_opt = self._recursive_bisection(cov, sorted_indices)

        weights = {}
        for i, idx in enumerate(sorted_indices):
            weights[symbols[idx]] = round(float(w_opt[i]), 6)

        sigma_p = float(np.sqrt(w_opt @ cov[np.ix_(sorted_indices, sorted_indices)] @ w_opt))
        div_ratio = float(1.0 / np.sum(w_opt ** 2)) if np.sum(w_opt ** 2) > 0 else 0.0

        logger.info(
            "HRP: symbols=%d vol=%.4f div=%.2f",
            N, sigma_p, div_ratio,
        )

        return PortfolioAllocation(
            weights=weights,
            expected_portfolio_return=round(0.0, 6),
            expected_portfolio_volatility=round(sigma_p, 6),
            sharpe_ratio=0.0,
            diversification_ratio=round(div_ratio, 2),
            method="hrp",
        )

    @staticmethod
    def _quasi_diag(linkage_matrix: np.ndarray, N: int) -> list[int]:
        sorted_idx = []

        def _walk(node):
            if node < N:
                sorted_idx.append(node)
            else:
                left = int(linkage_matrix[node - N, 0])
                right = int(linkage_matrix[node - N, 1])
                _walk(left)
                _walk(right)

        _walk(2 * N - 2)
        return sorted_idx

    @staticmethod
    def _recursive_bisection(cov: np.ndarray, indices: list[int]) -> np.ndarray:
        N = len(indices)
        if N == 1:
            return np.array([1.0])

        split = N // 2
        left_indices = indices[:split]
        right_indices = indices[split:]

        cov_left = cov[np.ix_(left_indices, left_indices)]
        cov_right = cov[np.ix_(right_indices, right_indices)]

        def cluster_variance(cov_sub):
            ivp = 1.0 / np.diag(cov_sub)
            w = ivp / ivp.sum()
            return float(w @ cov_sub @ w)

        var_left = cluster_variance(cov_left) if len(left_indices) > 0 else 0.0
        var_right = cluster_variance(cov_right) if len(right_indices) > 0 else 0.0

        alpha_left = var_right / (var_left + var_right) if (var_left + var_right) > 0 else 0.5
        alpha_right = 1 - alpha_left

        w_left = HRPOptimizer._recursive_bisection(cov, left_indices) * alpha_left
        w_right = HRPOptimizer._recursive_bisection(cov, right_indices) * alpha_right

        return np.concatenate([w_left, w_right])
