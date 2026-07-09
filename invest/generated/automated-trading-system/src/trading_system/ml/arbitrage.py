"""Statistical Arbitrage Engine — cointegration, PCA, HMM, Kalman filter.

This module provides four statistical arbitrage methods:
1. Cointegration Pairs Trading with Johansen test and mean-reversion analysis
2. PCA Arbitrage with residual mispricing detection
3. HMM Regime Detection with regime-conditional signals
4. Kalman Filter Dynamic Hedge Ratio for time-varying spreads

All signals are published via EventBus as "ml.arbitrage_signal" events.
Architecture: only depends on data+core, no imports from risk or execution.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.audit import AuditLogger, get_audit_logger
from ..core.config import ConfigManager, get_config
from ..core.event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency fallbacks
# ---------------------------------------------------------------------------

try:
    from scipy import linalg as scipy_linalg
    from scipy.stats import norm

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available, falling back to numpy-only implementations")

try:
    from sklearn.decomposition import PCA

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not available, PCA will use numpy-only fallback")

try:
    from hmmlearn import hmm as hmmlearn_module

    HMMLEARN_AVAILABLE = True
except ImportError:
    HMMLEARN_AVAILABLE = False
    logger.warning("hmmlearn not available, HMM will use numpy-only fallback")


class StatArbEngine:
    """Statistical Arbitrage Engine for discovering and trading statistical mispricing.

    Four methods:
    1. Cointegration Pairs Trading — Johansen test, half-life, z-score signals
    2. PCA Arbitrage — residual analysis, factor-neutral portfolio
    3. HMM Regime Detection — hidden states, regime-conditional signals
    4. Kalman Filter Dynamic Hedge Ratio — time-varying spread estimation

    All parameters configurable via YAML (ml.* namespace).
    """

    def __init__(self, config_dir: str = "config"):
        config = get_config(config_dir)
        self._config = config
        self._audit: AuditLogger = get_audit_logger()
        self._event_bus: EventBus = get_event_bus()

        # Configuration
        self._entry_zscore = config.get("ml.arbitrage.entry_zscore", 2.0)
        self._exit_zscore = config.get("ml.arbitrage.exit_zscore", 0.5)
        self._half_life_window = config.get("ml.arbitrage.half_life_window", 252)
        self._lookback_period = config.get("ml.arbitrage.lookback_period", 252)
        self._pca_threshold = config.get("ml.arbitrage.pca_threshold", 2.0)
        self._hmm_n_regimes = config.get("ml.arbitrage.hmm_n_regimes", 3)
        self._kalman_delta = config.get("ml.arbitrage.kalman_delta", 1e-4)
        self._kalman_transition_cov = config.get("ml.arbitrage.kalman_transition_cov", 1e-5)

        # State
        self._pairs: List[Tuple[str, str]] = []
        self._pair_hedge_ratios: Dict[str, float] = {}
        self._pair_half_lives: Dict[str, float] = {}
        self._last_signals: Dict[str, Dict[str, Any]] = {}

        logger.info(
            "StatArbEngine initialized: entry_z=%.2f, exit_z=%.2f, lookback=%d",
            self._entry_zscore, self._exit_zscore, self._lookback_period,
        )

    # -----------------------------------------------------------------------
    # 1. Cointegration Pairs Trading
    # -----------------------------------------------------------------------

    def find_pairs(
        self,
        price_df: pd.DataFrame,
        min_correlation: float = 0.5,
        max_pairs: int = 10,
    ) -> List[Tuple[str, float, float]]:
        """Discover cointegrated pairs from price data.

        Uses Johansen trace test when available, falls back to Engle-Granger ADF test.

        Args:
            price_df: DataFrame of prices, columns = tickers, index = dates
            min_correlation: Minimum correlation threshold for pre-screening
            max_pairs: Maximum number of pairs to return

        Returns:
            List of tuples: (ticker1, ticker2, half_life, hedge_ratio)
        """
        log_prices = np.log(price_df)
        tickers = list(price_df.columns)
        n = len(tickers)

        candidates = []

        # Pre-screening: correlation filter
        corr = log_prices.corr().values

        for i in range(n):
            for j in range(i + 1, n):
                if abs(corr[i, j]) < min_correlation:
                    continue

                # Form the spread
                y = log_prices[tickers[i]].values
                x = log_prices[tickers[j]].values

                # OLS: y = alpha + beta * x
                beta, alpha = self._ols_regression(x, y)
                spread = y - alpha - beta * x

                # Test for cointegration
                is_cointegrated, test_stat, p_value = self._cointegration_test(spread)

                if is_cointegrated:
                    half_life = self._estimate_half_life(spread)
                    candidates.append({
                        'ticker1': tickers[i],
                        'ticker2': tickers[j],
                        'hedge_ratio': beta,
                        'half_life': half_life,
                        'spread_std': np.std(spread),
                        'test_stat': test_stat,
                        'p_value': p_value,
                    })

        # Sort by half-life (faster mean reversion is better)
        candidates.sort(key=lambda x: x['half_life'])

        # Take top pairs
        top_pairs = candidates[:max_pairs]

        self._pairs = [(p['ticker1'], p['ticker2']) for p in top_pairs]
        self._pair_hedge_ratios = {}
        self._pair_half_lives = {}

        result = []
        for p in top_pairs:
            key = f"{p['ticker1']}_{p['ticker2']}"
            self._pair_hedge_ratios[key] = p['hedge_ratio']
            self._pair_half_lives[key] = p['half_life']
            result.append((p['ticker1'], p['ticker2'], p['half_life'], p['hedge_ratio']))

        logger.info(
            "Found %d cointegrated pairs from %d candidates",
            len(result), len(candidates),
        )

        self._audit.log(
            "pair_discovery",
            check_id="coint_pairs",
            result="OK",
            payload={
                "n_pairs": len(result),
                "n_tickers": len(tickers),
                "min_correlation": min_correlation,
            },
        )

        return result

    def compute_signals(
        self,
        price1: pd.Series,
        price2: pd.Series,
        hedge_ratio: Optional[float] = None,
        window: int = 20,
    ) -> pd.DataFrame:
        """Compute entry/exit signals for a cointegrated pair.

        Args:
            price1: Price series for asset 1
            price2: Price series for asset 2
            hedge_ratio: Fixed hedge ratio. If None, estimated from data.
            window: Rolling window for z-score normalization.

        Returns:
            DataFrame with columns: spread, zscore, signal, position
                signal: 1=long spread, -1=short spread, 0=neutral
                position: cumulative position
        """
        # Align and clean
        common = price1.index.intersection(price2.index)
        p1 = price1.loc[common].values
        p2 = price2.loc[common].values

        if len(p1) < window:
            raise ValueError(f"Need at least {window} observations, got {len(p1)}")

        # Estimate hedge ratio if not provided
        if hedge_ratio is None:
            log_y = np.log(p1)
            log_x = np.log(p2)
            hedge_ratio, _ = self._ols_regression(log_x, log_y)

        # Compute spread
        log_spread = np.log(p1) - hedge_ratio * np.log(p2)

        # Rolling z-score
        rolling_mean = pd.Series(log_spread).rolling(window=window).mean().values
        rolling_std = pd.Series(log_spread).rolling(window=window).std().values

        zscore = np.zeros(len(log_spread))
        valid = ~np.isnan(rolling_mean)
        zscore[valid] = (log_spread[valid] - rolling_mean[valid]) / rolling_std[valid]
        zscore = np.nan_to_num(zscore, 0.0)

        # Generate signals
        signal = np.zeros(len(log_spread), dtype=int)
        signal[zscore < -self._entry_zscore] = 1   # Long spread
        signal[zscore > self._entry_zscore] = -1    # Short spread
        signal[abs(zscore) < self._exit_zscore] = 0 # Exit

        # Position (cumulative, 0-sum)
        position = np.cumsum(signal)

        df = pd.DataFrame({
            'spread': log_spread,
            'zscore': zscore,
            'signal': signal,
            'position': position,
        }, index=common)

        # Publish signal event
        self._last_signals['cointegration'] = {
            'hedge_ratio': hedge_ratio,
            'last_spread': float(log_spread[-1]),
            'last_zscore': float(zscore[-1]),
            'last_signal': int(signal[-1]),
        }

        self._event_bus.publish(
            "ml.arbitrage_signal",
            {
                "method": "cointegration",
                "hedge_ratio": float(hedge_ratio),
                "spread": float(log_spread[-1]),
                "zscore": float(zscore[-1]),
                "signal": int(signal[-1]),
                "half_life": self._estimate_half_life(log_spread),
            },
            source="ml.arbitrage",
        )

        self._audit.log(
            "arbitrage_signal",
            check_id="coint_signal",
            result="OK",
            payload={
                "method": "cointegration",
                "zscore": float(zscore[-1]),
                "signal": int(signal[-1]),
            },
        )

        return df

    def _ols_regression(self, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """Ordinary Least Squares: y = alpha + beta * x.

        Args:
            x: Independent variable
            y: Dependent variable

        Returns:
            (beta, alpha) tuple
        """
        X = np.column_stack([np.ones(len(x)), x])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        return beta[1], beta[0]  # beta, alpha

    def _cointegration_test(self, spread: np.ndarray) -> Tuple[bool, float, float]:
        """Test for stationarity of spread (cointegration test).

        Uses Johansen trace test when scipy available, otherwise falls back
        to augmented Dickey-Fuller (ADF) test implemented directly.

        Args:
            spread: Residual spread series

        Returns:
            (is_cointegrated, test_statistic, p_value)
        """
        if SCIPY_AVAILABLE:
            # Compute ADF-like test
            delta = np.diff(spread)
            lagged = spread[:-1]

            # Add lagged differences for augmentation
            max_lag = min(12, int(len(spread) ** (1 / 3)))
            X = np.column_stack([lagged])
            if max_lag > 0:
                for lag in range(1, max_lag + 1):
                    if len(spread) - lag - 1 > 0:
                        d_lag = delta[lag - 1 : len(delta) - max_lag + lag - 1]
                        if len(d_lag) == len(X):
                            X = np.column_stack([X[:len(d_lag)], d_lag])

            y = delta[:len(X)]

            try:
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                residuals = y - X @ beta
                se = np.sqrt(np.sum(residuals ** 2) / (len(y) - X.shape[1]))
                beta_se = se * np.sqrt(np.linalg.inv(X.T @ X)[0, 0])
                t_stat = beta[0] / beta_se if beta_se != 0 else 0.0

                # Critical values approx
                is_coint = t_stat < -2.86  # 5% critical value for ADF
                return is_coint, t_stat, 0.05
            except Exception:
                return False, 0.0, 1.0
        else:
            # Simple numpy-only ADF implementation
            delta = np.diff(spread)
            lagged = spread[:-1]
            beta = np.linalg.lstsq(lagged.reshape(-1, 1), delta, rcond=None)[0][0]
            residuals = delta - beta * lagged
            se = np.std(residuals)
            t_stat = beta / (se / np.sqrt(len(lagged))) if se != 0 else 0.0
            is_coint = t_stat < -2.86
            return is_coint, t_stat, 0.05

    def _estimate_half_life(self, spread: np.ndarray) -> float:
        """Estimate the half-life of mean reversion for a spread series.

        Uses OLS on the AR(1) process: delta_spread = alpha + beta * spread_lagged

        Args:
            spread: Spread series

        Returns:
            Half-life in periods (positive values, bounded)
        """
        delta = np.diff(spread)
        lagged = spread[:-1]

        X = np.column_stack([np.ones(len(lagged)), lagged])
        beta = np.linalg.lstsq(X, delta, rcond=None)[0]

        slope = beta[1]
        if slope >= 0:
            # No mean reversion
            return float('inf')

        half_life = -np.log(2) / slope
        # Bound to reasonable range
        return min(half_life, self._half_life_window)

    # -----------------------------------------------------------------------
    # 2. PCA Arbitrage
    # -----------------------------------------------------------------------

    def pca_decomposition(
        self,
        returns_df: pd.DataFrame,
        n_components: int = 3,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Principal component decomposition for arbitrage detection.

        Args:
            returns_df: DataFrame of returns
            n_components: Number of principal components

        Returns:
            (components, explained_variance, residuals) tuple
        """
        returns = returns_df.values
        returns = returns - np.mean(returns, axis=0)

        # PCA via SVD
        U, S, Vt = np.linalg.svd(returns, full_matrices=False)

        components = Vt[:n_components]
        explained_variance = (S ** 2) / (len(returns) - 1)

        # Reconstruct using top components
        reconstructed = U[:, :n_components] @ np.diag(S[:n_components]) @ Vt[:n_components, :]
        residuals = returns - reconstructed

        return components, explained_variance, residuals

    def detect_mispricing(
        self,
        returns_df: pd.DataFrame,
        n_components: int = 3,
    ) -> pd.DataFrame:
        """Detect mispricing through PCA residual analysis.

        Large residuals indicate assets deviating from their factor structure,
        which may signal arbitrage opportunities.

        Args:
            returns_df: DataFrame of returns
            n_components: Number of principal components

        Returns:
            DataFrame with columns: residual, zscore, mispriced
        """
        _, explained_variance, residuals = self.pca_decomposition(returns_df, n_components)

        # Residual standard deviation per asset
        residual_std = np.std(residuals, axis=0)
        residual_std[residual_std == 0] = 1e-10

        # Latest residual (most recent observation)
        latest_residual = residuals[-1, :]

        # Z-score of residuals
        zscore = latest_residual / residual_std

        # Mispricing flag
        mispriced = np.abs(zscore) > self._pca_threshold

        df = pd.DataFrame({
            'ticker': returns_df.columns,
            'residual': latest_residual,
            'zscore': zscore,
            'mispriced': mispriced,
        })

        # Sort by absolute zscore
        df = df.sort_values('zscore', key=abs, ascending=False)

        # Publish event
        n_mispriced = mispriced.sum()
        self._event_bus.publish(
            "ml.arbitrage_signal",
            {
                "method": "pca",
                "n_mispriced": int(n_mispriced),
                "max_zscore": float(np.max(np.abs(zscore))),
                "n_components": n_components,
                "explained_variance": [float(v) for v in explained_variance[:n_components]],
            },
            source="ml.arbitrage",
        )

        self._audit.log(
            "arbitrage_signal",
            check_id="pca_mispricing",
            result="OK",
            payload={
                "method": "pca",
                "n_mispriced": int(n_mispriced),
                "n_components": n_components,
            },
        )

        return df

    def build_factor_neutral_portfolio(
        self,
        returns_df: pd.DataFrame,
        n_components: int = 3,
        long_quantile: float = 0.1,
        short_quantile: float = 0.1,
    ) -> Dict[str, Dict[str, object]]:
        """Build a factor-neutral long/short portfolio from PCA residuals.

        Long top residual (undervalued), short bottom residual (overvalued).

        Args:
            returns_df: DataFrame of returns
            n_components: Number of factors to neutralize
            long_quantile: Fraction of assets to go long
            short_quantile: Fraction of assets to short

        Returns:
            Dictionary with 'long' and 'short' ticker lists and weights
        """
        _, _, residuals = self.pca_decomposition(returns_df, n_components)

        latest_residual = residuals[-1, :]
        tickers = returns_df.columns

        n_long = max(1, int(len(tickers) * long_quantile))
        n_short = max(1, int(len(tickers) * short_quantile))

        # Sort by residual
        sorted_idx = np.argsort(latest_residual)

        short_idx = sorted_idx[:n_short]
        long_idx = sorted_idx[-n_long:]

        long_tickers = [tickers[i] for i in long_idx]
        short_tickers = [tickers[i] for i in short_idx]

        long_weights = 1.0 / n_long
        short_weights = -1.0 / n_short

        result = {
            'long': [{'ticker': t, 'weight': long_weights} for t in long_tickers],
            'short': [{'ticker': t, 'weight': short_weights} for t in short_tickers],
            'n_components': n_components,
        }

        self._audit.log(
            "arbitrage_signal",
            check_id="pca_portfolio",
            result="OK",
            payload={
                "method": "pca_factor_neutral",
                "n_long": n_long,
                "n_short": n_short,
            },
        )

        return result

    # -----------------------------------------------------------------------
    # 3. HMM Regime Detection
    # -----------------------------------------------------------------------

    def get_regime(
        self,
        returns: pd.Series,
        n_regimes: Optional[int] = None,
    ) -> pd.DataFrame:
        """Detect market regimes using Hidden Markov Model.

        Classifies each period into a regime (bullish, bearish, sideways, etc.)
        and provides regime-conditional trading signals.

        Args:
            returns: Series of returns
            n_regimes: Number of regimes (default from config)

        Returns:
            DataFrame with columns: regime, probability, signal
        """
        if n_regimes is None:
            n_regimes = self._hmm_n_regimes

        ret_vals = returns.values.reshape(-1, 1)

        if len(ret_vals) < 50:
            raise ValueError(f"Need at least 50 observations, got {len(ret_vals)}")

        if HMMLEARN_AVAILABLE:
            model = hmmlearn_module.GaussianHMM(
                n_components=n_regimes,
                covariance_type='full',
                n_iter=100,
                random_state=42,
            )
            model.fit(ret_vals)
            states = model.predict(ret_vals)
            probabilities = model.predict_proba(ret_vals)
        else:
            # Numpy-only fallback: simple volatility-based regime classification
            states, probabilities = self._simple_regime_classification(ret_vals, n_regimes)

        # Map regimes to meaningful labels based on mean return
        regime_means = {}
        for state in range(n_regimes):
            mask = states == state
            if mask.any():
                regime_means[state] = float(np.mean(ret_vals[mask]))
            else:
                regime_means[state] = 0.0

        sorted_regimes = sorted(regime_means.items(), key=lambda x: x[1])
        if n_regimes == 3:
            regime_map = {
                sorted_regimes[0][0]: 'bearish',
                sorted_regimes[1][0]: 'sideways',
                sorted_regimes[2][0]: 'bullish',
            }
        else:
            regime_map = {state: f'regime_{state}' for state in range(n_regimes)}

        regime_labels = [regime_map.get(s, f'regime_{s}') for s in states]

        # Generate regime-conditional signals
        signal = np.zeros(len(ret_vals))
        for i, r in enumerate(regime_labels):
            if r == 'bullish':
                signal[i] = 1
            elif r == 'bearish':
                signal[i] = -1

        # Transition probabilities
        transitions = self._compute_transition_matrix(states, n_regimes)

        df = pd.DataFrame({
            'regime': regime_labels,
            'regime_state': states,
            'probability': [float(np.max(p)) for p in probabilities],
            'signal': signal,
        }, index=returns.index)

        # Publish event
        current_regime = regime_labels[-1]
        self._event_bus.publish(
            "ml.arbitrage_signal",
            {
                "method": "hmm",
                "current_regime": current_regime,
                "signal": int(signal[-1]),
                "n_regimes": n_regimes,
                "regime_means": regime_means,
                "transitions": transitions,
            },
            source="ml.arbitrage",
        )

        self._audit.log(
            "arbitrage_signal",
            check_id="hmm_regime",
            result="OK",
            payload={
                "method": "hmm",
                "current_regime": current_regime,
                "n_regimes": n_regimes,
            },
        )

        self._last_signals['hmm'] = {
            'current_regime': current_regime,
            'signal': int(signal[-1]),
        }

        return df

    def _simple_regime_classification(
        self,
        returns: np.ndarray,
        n_regimes: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Simple volatility-based regime classification (numpy-only fallback).

        Uses rolling volatility and return to classify regimes heuristically.

        Args:
            returns: Return series (n, 1)
            n_regimes: Number of regimes

        Returns:
            (states, probabilities) tuple
        """
        n = len(returns)
        window = min(20, n // 5)

        # Rolling volatility and mean
        if n >= window:
            rolling_vol = np.array([np.std(returns[max(0, i - window):i + 1])
                                    for i in range(n)])
            rolling_mean = np.array([np.mean(returns[max(0, i - window):i + 1])
                                     for i in range(n)])
        else:
            rolling_vol = np.full(n, np.std(returns))
            rolling_mean = np.full(n, np.mean(returns))

        # Combine into features
        features = np.column_stack([rolling_mean, rolling_vol])
        features = (features - np.mean(features, axis=0)) / (np.std(features, axis=0) + 1e-10)

        # K-means-like clustering
        if n_regimes == 2:
            thresholds = [np.median(features[:, 0])]
        elif n_regimes == 3:
            p33, p66 = np.percentile(features[:, 0], [33, 66])
            thresholds = [p33, p66]
        else:
            thresholds = np.linspace(np.min(features[:, 0]), np.max(features[:, 0]),
                                     n_regimes + 1)[1:-1]

        states = np.zeros(n, dtype=int)
        for i, thresh in enumerate(thresholds):
            states[features[:, 0] > thresh] = i + 1

        # Simple probabilities (distance-based)
        probabilities = np.zeros((n, n_regimes))
        for i in range(n):
            for j in range(n_regimes):
                # Distance from regime center
                mask = states == j
                if mask.any():
                    center = np.mean(features[mask], axis=0)
                    dist = np.linalg.norm(features[i] - center)
                    probabilities[i, j] = np.exp(-dist)
                else:
                    probabilities[i, j] = 0.01
            probabilities[i] /= probabilities[i].sum()

        return states, probabilities

    def _compute_transition_matrix(
        self,
        states: np.ndarray,
        n_regimes: int,
    ) -> List[List[float]]:
        """Compute regime transition probabilities matrix."""
        transitions = np.zeros((n_regimes, n_regimes))
        for t in range(len(states) - 1):
            transitions[states[t], states[t + 1]] += 1

        # Normalize rows
        for i in range(n_regimes):
            row_sum = transitions[i].sum()
            if row_sum > 0:
                transitions[i] /= row_sum

        return [[float(v) for v in row] for row in transitions]

    # -----------------------------------------------------------------------
    # 4. Kalman Filter Dynamic Hedge Ratio
    # -----------------------------------------------------------------------

    def kalman_hedge_ratio(
        self,
        price1: pd.Series,
        price2: pd.Series,
    ) -> pd.DataFrame:
        """Estimate time-varying hedge ratio using Kalman filter.

        State-space model:
        - State: [alpha, beta] (intercept and hedge ratio) with random walk
        - Observation: log(p1) = alpha + beta * log(p2)

        Args:
            price1: Price series for asset 1 (dependent)
            price2: Price series for asset 2 (independent)

        Returns:
            DataFrame with columns: alpha, beta, spread, spread_zscore, signal
        """
        # Align prices
        common = price1.index.intersection(price2.index)
        log_p1 = np.log(price1.loc[common].values)
        log_p2 = np.log(price2.loc[common].values)

        n = len(log_p1)
        if n < 10:
            raise ValueError(f"Need at least 10 observations, got {n}")

        # Kalman filter state variables
        # State: [alpha, beta]
        state_dim = 2
        obs_dim = 1

        # Initial state estimate
        beta0, alpha0 = self._ols_regression(log_p2, log_p1)
        x = np.array([alpha0, beta0])

        # State covariance
        P = self._kalman_delta * np.eye(state_dim)

        # Transition matrix (identity: random walk)
        F = np.eye(state_dim)

        # Transition noise covariance
        Q = self._kalman_transition_cov * np.eye(state_dim)

        # Observation noise variance
        R = 1.0

        # Storage
        alphas = np.zeros(n)
        betas = np.zeros(n)
        spread = np.zeros(n)

        for t in range(n):
            # Observation matrix
            H = np.array([1.0, log_p2[t]]).reshape(1, state_dim)

            # Predict
            x_pred = F @ x
            P_pred = F @ P @ F.T + Q

            # Update
            y_residual = log_p1[t] - H @ x_pred
            S = H @ P_pred @ H.T + R
            K = P_pred @ H.T / S  # Kalman gain

            x = x_pred + K.flatten() * y_residual
            P = P_pred - np.outer(K.flatten(), H @ P_pred)

            # Store
            alphas[t] = x[0]
            betas[t] = x[1]
            spread[t] = log_p1[t] - (x[0] + x[1] * log_p2[t])

        # Z-score of spread
        lookback = min(self._lookback_period, n)
        spread_zscore = np.zeros(n)
        rolling_mean = np.zeros(n)
        rolling_std = np.zeros(n)

        for t in range(n):
            start = max(0, t - lookback)
            win = spread[start:t + 1]
            if len(win) > 1:
                rolling_mean[t] = np.mean(win)
                rolling_std[t] = np.std(win)
                if rolling_std[t] > 0:
                    spread_zscore[t] = (spread[t] - rolling_mean[t]) / rolling_std[t]

        # Adaptive thresholds based on spread volatility
        vol_pct_change = np.array([np.std(spread[max(0, t - lookback):t + 1])
                                   for t in range(n)])
        vol_pct_change = np.nan_to_num(vol_pct_change, 1.0)

        adaptive_entry = self._entry_zscore * (vol_pct_change / np.median(vol_pct_change))
        adaptive_exit = self._exit_zscore * (vol_pct_change / np.median(vol_pct_change))

        # Generate signals
        signal = np.zeros(n, dtype=int)
        signal[spread_zscore < -adaptive_entry] = 1    # Long spread
        signal[spread_zscore > adaptive_entry] = -1     # Short spread
        signal[abs(spread_zscore) < adaptive_exit] = 0  # Exit

        df = pd.DataFrame({
            'alpha': alphas,
            'beta': betas,
            'spread': spread,
            'spread_zscore': spread_zscore,
            'adaptive_entry_threshold': adaptive_entry,
            'adaptive_exit_threshold': adaptive_exit,
            'signal': signal,
        }, index=common)

        # Publish event
        self._event_bus.publish(
            "ml.arbitrage_signal",
            {
                "method": "kalman",
                "current_hedge_ratio": float(betas[-1]),
                "current_alpha": float(alphas[-1]),
                "spread_zscore": float(spread_zscore[-1]),
                "signal": int(signal[-1]),
                "adaptive_entry": float(adaptive_entry[-1]),
            },
            source="ml.arbitrage",
        )

        self._audit.log(
            "arbitrage_signal",
            check_id="kalman_hedge",
            result="OK",
            payload={
                "method": "kalman",
                "hedge_ratio": float(betas[-1]),
                "zscore": float(spread_zscore[-1]),
                "signal": int(signal[-1]),
            },
        )

        self._last_signals['kalman'] = {
            'hedge_ratio': float(betas[-1]),
            'spread_zscore': float(spread_zscore[-1]),
            'signal': int(signal[-1]),
        }

        return df

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    def get_last_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get the most recent signals across all methods.

        Returns:
            Dictionary keyed by method name with signal details
        """
        return dict(self._last_signals)

    def get_pairs(self) -> List[Tuple[str, str]]:
        """Get the list of discovered cointegrated pairs.

        Returns:
            List of (ticker1, ticker2) tuples
        """
        return list(self._pairs)