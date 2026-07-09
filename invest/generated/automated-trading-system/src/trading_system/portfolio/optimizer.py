"""Portfolio optimization — Markowitz Mean-Variance, Risk Parity, Hierarchical Risk Parity.

This module provides multiple portfolio optimization methods:
1. Markowitz Mean-Variance Optimization with multiple covariance estimators
2. Risk Parity (Equal Risk Contribution and Inverse Volatility Weighting)
3. Hierarchical Risk Parity (HRP) with correlation-based clustering

All methods follow the architectural constraints: only depends on data+core,
no imports from risk or execution layers. Configuration from YAML, events
published via EventBus, all significant operations audit-logged.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.audit import AuditLogger, get_audit_logger
from ..core.config import ConfigManager, get_config
from ..core.event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)

# Try to import optional dependencies with fallback
try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available, falling back to numpy-only implementations")

try:
    from sklearn.covariance import LedoitWolf
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not available, Ledoit-Wolf covariance will use fallback")


class PortfolioOptimizer:
    """Portfolio optimizer with multiple optimization methods.

    Supported methods:
    - markowitz: Mean-Variance optimization (max Sharpe, min variance, target return)
    - risk_parity: Equal risk contribution or inverse volatility weighting
    - hrp: Hierarchical Risk Parity

    All covariance estimates are configurable via config:
    - portfolio.covariance.method: 'sample', 'ledoit_wolf', or 'ewma'
    - portfolio.optimizer.risk_free_rate: Risk-free rate for Sharpe ratio
    - portfolio.optimizer.max_weight: Maximum weight per asset
    """

    SUPPORTED_METHODS = ['markowitz', 'risk_parity', 'hrp']
    COV_METHODS = ['sample', 'ledoit_wolf', 'ewma']

    def __init__(self, config_dir: str = "config"):
        config = get_config(config_dir)
        self._config = config
        self._audit: AuditLogger = get_audit_logger()
        self._event_bus: EventBus = get_event_bus()

        # Load configuration
        self._cov_method = config.get("portfolio.covariance.method", "sample")
        self._risk_free_rate = config.get("portfolio.optimizer.risk_free_rate", 0.02)
        self._max_weight = config.get("portfolio.optimizer.max_weight", 0.25)
        self._min_weight = config.get("portfolio.optimizer.min_weight", 0.0)
        self._ewma_lambda = config.get("portfolio.covariance.ewma_lambda", 0.94)

        # State
        self._weights: Optional[Dict[str, float]] = None
        self._weights_array: Optional[np.ndarray] = None
        self._tickers: Optional[List[str]] = None
        self._n_assets: int = 0
        self._last_returns: Optional[pd.DataFrame] = None
        self._cov_matrix: Optional[np.ndarray] = None
        self._mean_returns: Optional[np.ndarray] = None
        self._efficient_frontier: Optional[List[Tuple[float, float]]] = None

        logger.info(
            "PortfolioOptimizer initialized: cov_method=%s, max_weight=%.2f, rf=%.2f",
            self._cov_method, self._max_weight, self._risk_free_rate,
        )

    def optimize(
        self,
        returns_df: pd.DataFrame,
        method: str = 'markowitz',
        target_return: Optional[float] = None,
        objective: str = 'sharpe',
    ) -> Dict[str, float]:
        """Run portfolio optimization with specified method.

        Args:
            returns_df: DataFrame of asset returns, columns = tickers, index = dates
            method: Optimization method ('markowitz', 'risk_parity', 'hrp')
            target_return: Target annualized return for Markowitz (optional)
            objective: Objective for Markowitz ('sharpe', 'min_variance', 'target_return')

        Returns:
            Dictionary of {ticker: weight}

        Raises:
            ValueError: If method not supported or inputs invalid
        """
        if method not in self.SUPPORTED_METHODS:
            raise ValueError(f"Method {method} not supported. Use: {self.SUPPORTED_METHODS}")

        self._tickers = list(returns_df.columns)
        self._n_assets = len(self._tickers)
        self._last_returns = returns_df.copy()

        if self._n_assets < 2:
            raise ValueError("Need at least 2 assets for optimization")

        # Compute mean returns and covariance matrix
        self._mean_returns = returns_df.mean().values
        self._cov_matrix = self._compute_covariance(returns_df, self._cov_method)

        # Dispatch to optimization method
        if method == 'markowitz':
            weights = self._optimize_markowitz(objective, target_return)
        elif method == 'risk_parity':
            rp_method = self._config.get("portfolio.risk_parity.method", "equal_risk")
            weights = self._optimize_risk_parity(rp_method)
        elif method == 'hrp':
            weights = self._optimize_hrp()
        else:
            raise ValueError(f"Unknown method: {method}")

        # Store results
        self._weights_array = weights
        self._weights = dict(zip(self._tickers, weights))

        # Audit logging
        self._audit.log(
            "portfolio_optimization",
            check_id=f"opt_{method}",
            result="OK",
            actor="system",
            payload={
                "method": method,
                "n_assets": self._n_assets,
                "objective": objective if method == 'markowitz' else None,
            },
        )

        # Publish event
        self._event_bus.publish(
            "portfolio.optimization_complete",
            {
                "method": method,
                "n_assets": self._n_assets,
                "max_weight": float(np.max(weights)),
                "min_weight": float(np.min(weights)),
                "expected_return": float(self._expected_return(weights)),
                "portfolio_variance": float(self._portfolio_variance(weights)),
            },
            source="portfolio.optimizer",
        )

        logger.info(
            "Optimization complete: method=%s, n_assets=%d, exp_return=%.4f, volatility=%.4f",
            method, self._n_assets,
            float(self._expected_return(weights)),
            float(np.sqrt(self._portfolio_variance(weights))),
        )

        return self._weights

    def get_weights(self) -> Optional[Dict[str, float]]:
        """Get the most recent optimized weights.

        Returns:
            Dictionary {ticker: weight} or None if no optimization run yet
        """
        return self._weights

    def get_weights_array(self) -> Optional[np.ndarray]:
        """Get the most recent optimized weights as numpy array."""
        return self._weights_array

    def get_efficient_frontier(
        self,
        returns_df: pd.DataFrame,
        n_points: int = 20,
    ) -> List[Tuple[float, float]]:
        """Compute the efficient frontier for given returns.

        Args:
            returns_df: DataFrame of asset returns
            n_points: Number of points on the frontier

        Returns:
            List of (volatility, return) pairs
        """
        mean_returns = returns_df.mean().values
        cov_matrix = self._compute_covariance(returns_df, self._cov_method)
        n_assets = len(returns_df.columns)

        min_ret = np.min(mean_returns)
        max_ret = np.max(mean_returns)
        target_returns = np.linspace(min_ret, max_ret, n_points)

        frontier = []

        for target in target_returns:
            constraints = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},
                {'type': 'eq', 'fun': lambda w: self._expected_return(w, mean_returns) - target},
            ]
            bounds = [(self._min_weight, self._max_weight) for _ in range(n_assets)]
            init_guess = np.array([1.0 / n_assets] * n_assets)

            try:
                if SCIPY_AVAILABLE:
                    result = minimize(
                        self._portfolio_variance,
                        init_guess,
                        args=(cov_matrix,),
                        method='SLSQP',
                        bounds=bounds,
                        constraints=constraints,
                    )
                    if result.success:
                        weights = result.x
                        var = self._portfolio_variance(weights, cov_matrix)
                        ret = self._expected_return(weights, mean_returns)
                        frontier.append((np.sqrt(var), ret))
                else:
                    weights = np.array([1.0 / n_assets] * n_assets)
                    var = self._portfolio_variance(weights, cov_matrix)
                    ret = self._expected_return(weights, mean_returns)
                    frontier.append((np.sqrt(var), ret))
            except Exception as e:
                logger.warning("Failed to compute frontier point at %.4f: %s", target, e)
                continue

        self._efficient_frontier = frontier
        return frontier

    def _compute_covariance(
        self,
        returns: pd.DataFrame,
        method: str,
    ) -> np.ndarray:
        """Compute covariance matrix with specified method.

        Args:
            returns: Returns DataFrame
            method: 'sample', 'ledoit_wolf', or 'ewma'

        Returns:
            Covariance matrix as numpy array
        """
        if method == 'sample':
            return np.cov(returns.T, ddof=1)
        elif method == 'ledoit_wolf' and SKLEARN_AVAILABLE:
            lw = LedoitWolf()
            lw.fit(returns)
            return lw.covariance_
        elif method == 'ledoit_wolf' and not SKLEARN_AVAILABLE:
            sample_cov = np.cov(returns.T, ddof=1)
            n, p = returns.shape
            avg_var = np.mean(np.diag(sample_cov))
            shrinkage = 0.2
            shrunk = (1 - shrinkage) * sample_cov + shrinkage * avg_var * np.eye(p)
            return shrunk
        elif method == 'ewma':
            n, p = returns.shape
            returns_arr = returns.values
            weights = np.array([(1 - self._ewma_lambda) * (self._ewma_lambda ** i)
                               for i in reversed(range(n))])
            weights /= weights.sum()

            mean = np.average(returns_arr, axis=0, weights=weights)
            centered = returns_arr - mean
            cov = np.zeros((p, p))
            for i in range(p):
                for j in range(p):
                    cov[i, j] = np.sum(weights * centered[:, i] * centered[:, j])
            return cov
        else:
            logger.warning("Unknown covariance method %s, falling back to sample", method)
            return np.cov(returns.T, ddof=1)

    def _expected_return(
        self,
        weights: np.ndarray,
        mean_returns: Optional[np.ndarray] = None,
    ) -> float:
        """Compute expected portfolio return."""
        if mean_returns is None:
            mean_returns = self._mean_returns
        return float(np.sum(weights * mean_returns))

    def _portfolio_variance(
        self,
        weights: np.ndarray,
        cov_matrix: Optional[np.ndarray] = None,
    ) -> float:
        """Compute portfolio variance."""
        if cov_matrix is None:
            cov_matrix = self._cov_matrix
        return float(weights.T @ cov_matrix @ weights)

    def _portfolio_volatility(
        self,
        weights: np.ndarray,
        cov_matrix: Optional[np.ndarray] = None,
    ) -> float:
        """Compute portfolio volatility (std dev)."""
        return np.sqrt(self._portfolio_variance(weights, cov_matrix))

    def _sharpe_ratio(
        self,
        weights: np.ndarray,
        mean_returns: Optional[np.ndarray] = None,
        cov_matrix: Optional[np.ndarray] = None,
    ) -> float:
        """Compute Sharpe ratio (excess return over volatility)."""
        ret = self._expected_return(weights, mean_returns)
        vol = self._portfolio_volatility(weights, cov_matrix)
        if vol == 0:
            return 0.0
        daily_rf = (1 + self._risk_free_rate) ** (1/252) - 1
        excess_ret = ret - daily_rf
        return excess_ret / vol

    def _optimize_markowitz(
        self,
        objective: str,
        target_return: Optional[float],
    ) -> np.ndarray:
        """Markowitz Mean-Variance optimization."""
        n = self._n_assets
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(self._min_weight, self._max_weight) for _ in range(n)]
        init_guess = np.array([1.0 / n] * n)

        if SCIPY_AVAILABLE:
            if objective == 'sharpe':
                def objective_func(w):
                    return -self._sharpe_ratio(w)

                result = minimize(
                    objective_func,
                    init_guess,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints,
                )
                if not result.success:
                    logger.warning("Max Sharpe optimization failed: %s", result.message)
                    return init_guess
                return result.x

            elif objective == 'min_variance':
                def objective_func(w):
                    return self._portfolio_variance(w)

                result = minimize(
                    objective_func,
                    init_guess,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints,
                )
                if not result.success:
                    logger.warning("Min variance optimization failed: %s", result.message)
                    return init_guess
                return result.x

            elif objective == 'target_return' and target_return is not None:
                if target_return > 1:
                    target_return = target_return / 100
                daily_target = (1 + target_return) ** (1/252) - 1
                constraints.append({
                    'type': 'eq',
                    'fun': lambda w: self._expected_return(w) - daily_target
                })

                result = minimize(
                    self._portfolio_variance,
                    init_guess,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints,
                )
                if not result.success:
                    logger.warning("Target return optimization failed: %s", result.message)
                    return init_guess
                return result.x

            else:
                logger.warning("Unknown objective %s, defaulting to max Sharpe", objective)
                return self._optimize_markowitz('sharpe', None)
        else:
            logger.warning("scipy not available, using equal weights (fallback)")
            return np.array([1.0 / n] * n)

    def _optimize_risk_parity(self, method: str) -> np.ndarray:
        """Risk Parity optimization."""
        if method == 'inverse_volatility':
            vols = np.sqrt(np.diag(self._cov_matrix))
            inv_vols = 1.0 / vols
            weights = inv_vols / np.sum(inv_vols)
            weights = np.clip(weights, self._min_weight, self._max_weight)
            weights /= np.sum(weights)
            return weights

        elif method == 'equal_risk':
            n = self._n_assets
            init_guess = np.array([1.0 / n] * n)
            bounds = [(self._min_weight, self._max_weight) for _ in range(n)]
            constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]

            def risk_contribution(weights: np.ndarray) -> np.ndarray:
                sigma = np.sqrt(weights.T @ self._cov_matrix @ weights)
                marginal = (self._cov_matrix @ weights) / sigma
                rc = weights * marginal
                return rc

            def objective_func(w: np.ndarray) -> float:
                rc = risk_contribution(w)
                target = np.sum(rc) / len(rc)
                return np.sum((rc - target) ** 2)

            if SCIPY_AVAILABLE:
                result = minimize(
                    objective_func,
                    init_guess,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints,
                )
                if result.success:
                    return result.x
                else:
                    logger.warning("Equal risk optimization failed: %s, falling back to inverse vol",
                                 result.message)
                    return self._optimize_risk_parity('inverse_volatility')
            else:
                logger.warning("scipy not available, falling back to inverse volatility weighting")
                return self._optimize_risk_parity('inverse_volatility')
        else:
            logger.warning("Unknown risk parity method %s, using inverse volatility", method)
            return self._optimize_risk_parity('inverse_volatility')

    def _cluster_hierarchical(self, corr: np.ndarray) -> List[int]:
        """Hierarchical clustering based on correlation distance.

        Numpy-only single-linkage agglomerative clustering.

        Args:
            corr: Correlation matrix

        Returns:
            Sorted indices for HRP recursive bisection
        """
        n = corr.shape[0]
        dist = np.sqrt(0.5 * (1 - corr))

        clusters = [[i] for i in range(n)]

        while len(clusters) > 1:
            min_dist = float('inf')
            merge_i = 0
            merge_j = 1

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    avg_d = 0
                    count = 0
                    for a in clusters[i]:
                        for b in clusters[j]:
                            avg_d += dist[a, b]
                            count += 1
                    avg_d /= count

                    if avg_d < min_dist:
                        min_dist = avg_d
                        merge_i = i
                        merge_j = j

            merged = clusters[merge_i] + clusters[merge_j]
            new_clusters = []
            for k, c in enumerate(clusters):
                if k != merge_i and k != merge_j:
                    new_clusters.append(c)
            new_clusters.append(merged)
            clusters = new_clusters

        if clusters:
            return clusters[0]
        else:
            return list(range(n))

    def _recursive_bisection(
        self,
        cov: np.ndarray,
        sorted_indices: List[int],
    ) -> np.ndarray:
        """Recursive bisection allocation for HRP."""
        n = len(sorted_indices)
        weights = np.ones(n)
        self._bisect_allocation(cov, sorted_indices, weights)
        return weights[sorted_indices] / np.sum(weights[sorted_indices])

    def _bisect_allocation(
        self,
        cov: np.ndarray,
        cluster: List[int],
        weights: np.ndarray,
    ) -> None:
        """Recursive bisection for HRP."""
        if len(cluster) == 1:
            return

        mid = len(cluster) // 2
        left = cluster[:mid]
        right = cluster[mid:]

        left_cov = cov[np.ix_(left, left)]
        right_cov = cov[np.ix_(right, right)]

        left_var = np.sum(left_cov)
        right_var = np.sum(right_cov)

        alpha = right_var / (left_var + right_var)

        for idx in left:
            weights[idx] *= alpha
        for idx in right:
            weights[idx] *= (1 - alpha)

        self._bisect_allocation(cov, left, weights)
        self._bisect_allocation(cov, right, weights)

    def _optimize_hrp(self) -> np.ndarray:
        """Hierarchical Risk Parity optimization."""
        vols = np.sqrt(np.diag(self._cov_matrix))
        corr = self._cov_matrix / np.outer(vols, vols)

        sorted_indices = self._cluster_hierarchical(corr)

        weights = self._recursive_bisection(self._cov_matrix, sorted_indices)

        weights = np.clip(weights, self._min_weight, self._max_weight)
        weights /= np.sum(weights)

        return weights

    def factor_exposure_analysis(
        self,
        factor_returns: pd.DataFrame,
        portfolio_returns: Optional[pd.Series] = None,
    ) -> Dict[str, float]:
        """Analyze factor exposure of the current optimized portfolio.

        Args:
            factor_returns: DataFrame of factor returns (same time index as asset returns)
            portfolio_returns: Optional pre-computed portfolio returns

        Returns:
            Dictionary of factor betas and R-squared
        """
        if self._weights is None or self._last_returns is None:
            raise ValueError("No optimization has been run yet")

        if portfolio_returns is None:
            portfolio_returns = self._last_returns @ list(self._weights.values())

        X = factor_returns.values
        y = portfolio_returns.values
        n = len(y)

        X = np.hstack([np.ones((n, 1)), X])

        try:
            beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)
        except Exception as e:
            logger.error("Factor exposure analysis failed: %s", e)
            return {}

        y_hat = X @ beta
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        result = {'r_squared': float(r_squared)}
        factor_names = ['intercept'] + list(factor_returns.columns)
        for name, b in zip(factor_names, beta):
            result[f'beta_{name}'] = float(b)

        self._audit.log(
            "factor_exposure_analysis",
            check_id="hrp_factor",
            result="OK",
            payload={"n_factors": len(factor_returns.columns), "r_squared": r_squared},
        )

        return result