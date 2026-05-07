import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CovarianceResult:
    covariance_matrix: pd.DataFrame
    correlation_matrix: pd.DataFrame
    shrinkage_intensity: float
    method: str
    is_positive_definite: bool


class CovarianceEstimator:
    def __init__(self, min_samples_multiplier: int = 2):
        self._min_samples_multiplier = min_samples_multiplier
        self._cache: dict[str, CovarianceResult] = {}

    def estimate(
        self,
        returns_df: pd.DataFrame,
        method: str = "ledoit_wolf",
        force_shrinkage: bool = False,
    ) -> CovarianceResult:
        T, N = returns_df.shape
        force_shrinkage = force_shrinkage or (T < N * self._min_samples_multiplier)

        if method == "sample":
            result = self._sample_covariance(returns_df, force_shrinkage)
        elif method == "exponential":
            result = self._exponential_covariance(returns_df, force_shrinkage)
        elif method == "ledoit_wolf":
            result = self._ledoit_wolf(returns_df)
        else:
            raise ValueError(f"Unknown method: {method}. Supported: sample, exponential, ledoit_wolf")

        return result

    def _sample_covariance(
        self, returns_df: pd.DataFrame, force_shrinkage: bool
    ) -> CovarianceResult:
        if force_shrinkage:
            logger.info("Forcing shrinkage due to insufficient samples")
            return self._ledoit_wolf(returns_df)

        cov = returns_df.cov().values
        corr = returns_df.corr().values
        cov_df = pd.DataFrame(cov, index=returns_df.columns, columns=returns_df.columns)
        corr_df = pd.DataFrame(corr, index=returns_df.columns, columns=returns_df.columns)

        is_pd = self._is_positive_definite(cov)
        if not is_pd:
            logger.warning("Sample covariance not positive definite, falling back to Ledoit-Wolf")
            return self._ledoit_wolf(returns_df)

        return CovarianceResult(
            covariance_matrix=cov_df,
            correlation_matrix=corr_df,
            shrinkage_intensity=0.0,
            method="sample",
            is_positive_definite=is_pd,
        )

    def _exponential_covariance(
        self, returns_df: pd.DataFrame, force_shrinkage: bool, half_life: int = 60
    ) -> CovarianceResult:
        if force_shrinkage:
            logger.info("Forcing shrinkage due to insufficient samples")
            return self._ledoit_wolf(returns_df)

        decay_factor = 0.5 ** (1.0 / half_life)
        T = len(returns_df)
        weights = np.array([decay_factor ** (T - 1 - i) for i in range(T)])
        weights = weights / weights.sum()

        demeaned = returns_df.values - np.average(returns_df.values, axis=0, weights=weights)
        cov = (demeaned.T * weights) @ demeaned
        std = np.sqrt(np.diag(cov))
        outer_std = np.outer(std, std)
        outer_std[outer_std == 0] = 1e-10
        corr = cov / outer_std

        cov_df = pd.DataFrame(cov, index=returns_df.columns, columns=returns_df.columns)
        corr_df = pd.DataFrame(corr, index=returns_df.columns, columns=returns_df.columns)

        is_pd = self._is_positive_definite(cov)
        return CovarianceResult(
            covariance_matrix=cov_df,
            correlation_matrix=corr_df,
            shrinkage_intensity=0.0,
            method="exponential",
            is_positive_definite=is_pd,
        )

    def _ledoit_wolf(self, returns_df: pd.DataFrame) -> CovarianceResult:
        T, N = returns_df.shape
        returns = returns_df.values

        sample_cov = np.cov(returns, rowvar=False, ddof=1)

        if T <= 1 or N <= 1:
            cov_df = pd.DataFrame(
                np.diag(np.diag(sample_cov)),
                index=returns_df.columns, columns=returns_df.columns,
            )
            corr_df = pd.DataFrame(np.eye(N), index=returns_df.columns, columns=returns_df.columns)
            return CovarianceResult(
                covariance_matrix=cov_df,
                correlation_matrix=corr_df,
                shrinkage_intensity=1.0,
                method="ledoit_wolf",
                is_positive_definite=True,
            )

        sample_corr = np.corrcoef(returns, rowvar=False)
        np.fill_diagonal(sample_corr, 0)
        avg_corr = np.sum(sample_corr) / (N * (N - 1)) if N > 1 else 0.0

        sqrt_diag = np.sqrt(np.diag(sample_cov))
        shrinkage_target = np.outer(sqrt_diag, sqrt_diag) * avg_corr
        np.fill_diagonal(shrinkage_target, np.diag(sample_cov))

        y = returns ** 2
        phi_mat = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                phi_mat[i, j] = np.mean((y[:, i] - sample_cov[i, i]) * (y[:, j] - sample_cov[j, j]))

        pi_hat = np.sum(phi_mat)

        gamma_hat = np.sum((sample_cov - shrinkage_target) ** 2)

        shrinkage_intensity = pi_hat / gamma_hat / T if gamma_hat > 0 else 0.0
        shrinkage_intensity = max(0.0, min(1.0, shrinkage_intensity))

        shrunk_cov = shrinkage_intensity * shrinkage_target + (1 - shrinkage_intensity) * sample_cov

        diag_sqrt = np.sqrt(np.diag(shrunk_cov))
        outer = np.outer(diag_sqrt, diag_sqrt)
        outer[outer == 0] = 1e-10
        shrunk_corr = shrunk_cov / outer

        cov_df = pd.DataFrame(shrunk_cov, index=returns_df.columns, columns=returns_df.columns)
        corr_df = pd.DataFrame(shrunk_corr, index=returns_df.columns, columns=returns_df.columns)

        is_pd = self._is_positive_definite(shrunk_cov)

        logger.info(
            "Ledoit-Wolf: shrinkage_intensity=%.4f, N=%d, T=%d, is_pd=%s",
            shrinkage_intensity, N, T, is_pd,
        )

        return CovarianceResult(
            covariance_matrix=cov_df,
            correlation_matrix=corr_df,
            shrinkage_intensity=round(shrinkage_intensity, 6),
            method="ledoit_wolf",
            is_positive_definite=is_pd,
        )

    @staticmethod
    def _is_positive_definite(matrix: np.ndarray) -> bool:
        try:
            eigvals = np.linalg.eigvalsh(matrix)
            return bool(np.all(eigvals > 1e-10))
        except np.linalg.LinAlgError:
            return False

    def get_cached(self, key: str) -> Optional[CovarianceResult]:
        return self._cache.get(key)

    def set_cached(self, key: str, result: CovarianceResult) -> None:
        self._cache[key] = result
