import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HedgeRatioEstimate:
    beta: float
    beta_std: float
    residual: float

    @property
    def is_uncertain(self) -> bool:
        return self.beta_std > 0.1


class KalmanHedgeRatio:
    def __init__(
        self,
        delta: float = 1e-4,
        sigma_obs: float = 0.01,
        initial_beta: float = 1.0,
        initial_cov: float = 1.0,
    ):
        self._delta = delta
        self._sigma_obs_sq = sigma_obs ** 2
        self._beta = initial_beta
        self._cov = initial_cov
        self._n_updates = 0

    def update(self, y: float, x: float) -> HedgeRatioEstimate:
        x_val = x if abs(x) > 1e-10 else 1e-10

        beta_pred = self._beta
        cov_pred = self._cov + self._delta

        residual = y - beta_pred * x_val

        S = x_val * cov_pred * x_val + self._sigma_obs_sq
        K = cov_pred * x_val / S if S > 0 else 0.0

        self._beta = beta_pred + K * residual
        self._cov = (1 - K * x_val) * cov_pred
        self._n_updates += 1

        beta_std = float(np.sqrt(max(self._cov, 0.0)))

        if self._n_updates <= 10:
            logger.debug(
                "Kalman update %d: y=%.4f x=%.4f beta=%.4f±%.4f res=%.4f",
                self._n_updates, y, x, self._beta, beta_std, residual,
            )

        return HedgeRatioEstimate(
            beta=round(float(self._beta), 6),
            beta_std=round(float(beta_std), 6),
            residual=round(float(residual), 6),
        )

    def batch_update(self, y_series: np.ndarray, x_series: np.ndarray) -> HedgeRatioEstimate:
        result = None
        for y, x in zip(y_series, x_series):
            result = self.update(float(y), float(x))
        return result if result is not None else HedgeRatioEstimate(
            beta=self._beta, beta_std=float(np.sqrt(max(self._cov, 0.0))), residual=0.0,
        )

    def reset(self, initial_beta: float = 1.0, initial_cov: float = 1.0) -> None:
        self._beta = initial_beta
        self._cov = initial_cov
        self._n_updates = 0

    @property
    def beta(self) -> float:
        return float(self._beta)

    @property
    def beta_std(self) -> float:
        return float(np.sqrt(max(self._cov, 0.0)))

    @property
    def n_updates(self) -> int:
        return self._n_updates
