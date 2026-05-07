import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

logger = logging.getLogger(__name__)


@dataclass
class FactorExposure:
    factor_exposures: dict[str, dict[str, float]]
    factor_returns: dict[str, float]
    contribution_returns: dict[str, float]
    specific_return: float
    total_return: float
    alpha_ratio: float

    @property
    def alpha_pct(self) -> float:
        return self.alpha_ratio * 100


@dataclass
class FactorModelResult:
    pca_factors: pd.DataFrame
    fundamental_factors: dict[str, pd.Series]
    combined_factors: pd.DataFrame
    explained_variance_ratio: list[float]
    factor_names: list[str]


class FactorModel:
    def __init__(self, n_pca_components: int = 5, explained_variance_threshold: float = 0.80):
        self._n_pca_components = n_pca_components
        self._explained_variance_threshold = explained_variance_threshold
        self._factor_names: list[str] = []
        self._factor_returns: Optional[pd.DataFrame] = None
        self._pca_model: Optional[PCA] = None

    def fit(
        self,
        returns_df: pd.DataFrame,
        fundamental_df: Optional[pd.DataFrame] = None,
    ) -> FactorModelResult:
        T, N = returns_df.shape

        pca = PCA(n_components=min(self._n_pca_components, N, T))
        pca.fit(returns_df.values)
        self._pca_model = pca

        cumulative_variance = np.cumsum(pca.explained_variance_ratio_)
        n_components = int(np.searchsorted(cumulative_variance, self._explained_variance_threshold) + 1)
        n_components = max(1, min(n_components, self._n_pca_components, N, T))

        pca_scores = pca.transform(returns_df.values)[:, :n_components]
        pca_names = [f"PCA_{i+1}" for i in range(n_components)]
        pca_factors = pd.DataFrame(pca_scores, index=returns_df.index, columns=pca_names)

        factor_names = list(pca_names)
        combined = pca_factors.copy()

        if fundamental_df is not None and not fundamental_df.empty:
            if "market_beta" in fundamental_df.columns:
                market_idx = fundamental_df.columns.get_loc("market_beta")
                combined["market_beta"] = fundamental_df["market_beta"]
                factor_names.append("market_beta")
            if "size" in fundamental_df.columns:
                combined["size"] = fundamental_df["size"]
                factor_names.append("size")
            if "momentum" in fundamental_df.columns:
                combined["momentum"] = fundamental_df["momentum"]
                factor_names.append("momentum")
            if "volatility" in fundamental_df.columns:
                combined["volatility"] = fundamental_df["volatility"]
                factor_names.append("volatility")

            sector_cols = [c for c in fundamental_df.columns if c.startswith("sector_")]
            for col in sector_cols:
                combined[col] = fundamental_df[col]
                factor_names.append(col)

        self._factor_names = factor_names
        self._factor_returns = combined

        logger.info(
            "Factor model fitted: %d factors, PCA explains %.1f%% variance",
            len(factor_names), cumulative_variance[min(n_components - 1, len(cumulative_variance) - 1)] * 100,
        )

        return FactorModelResult(
            pca_factors=pca_factors,
            fundamental_factors={},
            combined_factors=combined,
            explained_variance_ratio=list(pca.explained_variance_ratio_[:n_components]),
            factor_names=factor_names,
        )

    def get_factor_exposures(
        self,
        portfolio_weights: dict[str, float],
        returns_df: pd.DataFrame,
    ) -> FactorExposure:
        if self._factor_returns is None or self._pca_model is None:
            raise ValueError("Factor model not fitted. Call fit() first.")

        symbols = list(portfolio_weights.keys())
        weights_array = np.array([portfolio_weights[s] for s in symbols])

        portfolio_returns = (returns_df[symbols] * weights_array).sum(axis=1)

        factor_data = self._factor_returns.loc[returns_df.index]

        from sklearn.linear_model import LinearRegression
        reg = LinearRegression()
        reg.fit(factor_data.values, portfolio_returns.values)

        factor_exposures = {}
        contribution_returns = {}
        for i, name in enumerate(self._factor_names):
            exposure = float(reg.coef_[i])
            factor_return = float(factor_data[name].mean()) * 252
            contribution = exposure * factor_return
            factor_exposures[name] = {
                "exposure": round(exposure, 6),
                "factor_return_annualized": round(factor_return, 6),
                "contribution_annualized": round(contribution, 6),
            }
            contribution_returns[name] = round(contribution, 6)

        total_return = float(portfolio_returns.mean() * 252)
        specific_return = total_return - sum(contribution_returns.values())
        alpha_ratio = abs(specific_return) / (abs(total_return) + 1e-10)

        logger.info(
            "Factor exposure: total_return=%.4f alpha=%.4f alpha_ratio=%.1f%%",
            total_return, specific_return, alpha_ratio * 100,
        )

        return FactorExposure(
            factor_exposures=factor_exposures,
            factor_returns={name: round(float(factor_data[name].mean() * 252), 6) for name in self._factor_names},
            contribution_returns=contribution_returns,
            specific_return=round(specific_return, 6),
            total_return=round(total_return, 6),
            alpha_ratio=round(alpha_ratio, 6),
        )

    def hedge(
        self,
        portfolio_weights: dict[str, float],
        hedge_factors: list[str],
        returns_df: pd.DataFrame,
    ) -> dict[str, float]:
        if self._factor_returns is None:
            raise ValueError("Factor model not fitted. Call fit() first.")

        symbols = list(portfolio_weights.keys())
        weights_array = np.array([portfolio_weights[s] for s in symbols])

        factor_data = self._factor_returns.loc[returns_df.index]
        factor_subset = factor_data[hedge_factors].values

        excess_returns = returns_df[symbols].values - returns_df[symbols].values.mean(axis=0)

        hedged_weights = weights_array.copy()
        for j, factor_name in enumerate(hedge_factors):
            factor_col = factor_subset[:, j]
            betas = np.array([
                np.cov(excess_returns[:, i], factor_col)[0, 1] / np.var(factor_col)
                if np.var(factor_col) > 0 else 0.0
                for i in range(len(symbols))
            ])
            exposure = np.dot(weights_array, betas)
            if exposure != 0:
                adjustment = -exposure * betas / len(symbols)
                hedged_weights = hedged_weights + adjustment

        hedged_weights = np.maximum(hedged_weights, 0)
        hedged_weights = hedged_weights / hedged_weights.sum()

        result = {s: round(float(hedged_weights[i]), 6) for i, s in enumerate(symbols)}
        logger.info("Hedged factors: %s, weights adjusted", hedge_factors)
        return result

    @property
    def factor_names(self) -> list[str]:
        return list(self._factor_names)

    @property
    def factor_returns(self) -> Optional[pd.DataFrame]:
        return self._factor_returns
