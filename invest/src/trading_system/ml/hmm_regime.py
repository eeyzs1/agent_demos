import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class HMMRegimeResult:
    current_regime: int
    state_probabilities: list[float]
    regime_characteristics: dict[int, dict]
    transition_matrix: np.ndarray
    feature_names: list[str]

    @property
    def dominant_regime_label(self) -> str:
        if self.regime_characteristics and self.current_regime in self.regime_characteristics:
            return self.regime_characteristics[self.current_regime].get("label", f"State_{self.current_regime}")
        return f"State_{self.current_regime}"


class HMMRegimeDetector:
    def __init__(
        self,
        n_components: int = 3,
        covariance_type: str = "full",
        n_iter: int = 100,
        random_state: int = 42,
        model_dir: str = "./data/models/hmm",
    ):
        self._n_components = n_components
        self._covariance_type = covariance_type
        self._n_iter = n_iter
        self._random_state = random_state
        self._model_dir = Path(model_dir)
        self._model_dir.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._feature_names: list[str] = []
        self._regime_characteristics: dict[int, dict] = {}
        self._last_trained: Optional[datetime] = None

    def prepare_features(
        self,
        data: pd.DataFrame,
        market_breadth: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        if "close" not in data.columns:
            raise ValueError("Data must contain 'close' column")

        close = data["close"]
        returns = close.pct_change()

        features = pd.DataFrame(index=data.index)
        features["ret_5d"] = close.pct_change(5)
        features["ret_20d"] = close.pct_change(20)
        features["vol_5d"] = returns.rolling(5).std()
        features["vol_20d"] = returns.rolling(20).std()
        features["trend_strength"] = features["ret_5d"] - features["ret_20d"]

        if market_breadth is not None:
            features["breadth"] = market_breadth
        else:
            features["breadth"] = 0.5

        self._feature_names = list(features.columns)
        return features.dropna()

    def fit(
        self,
        features: pd.DataFrame,
        train_start: Optional[str] = None,
        train_end: Optional[str] = None,
    ) -> bool:
        from hmmlearn.hmm import GaussianHMM

        if train_start is not None:
            features = features.loc[train_start:]
        if train_end is not None:
            features = features.loc[:train_end]

        if len(features) < 500:
            logger.warning("Insufficient data for HMM training: %d rows < 500", len(features))
            return False

        try:
            model = GaussianHMM(
                n_components=self._n_components,
                covariance_type=self._covariance_type,
                n_iter=self._n_iter,
                random_state=self._random_state,
            )
            model.fit(features.values)
            self._model = model
            self._last_trained = datetime.now()

            states = model.predict(features.values)

            self._regime_characteristics = {}
            for state in range(self._n_components):
                state_returns = features["ret_20d"].values[states == state]
                state_vol = features["vol_20d"].values[states == state]
                avg_ret = float(np.mean(state_returns)) if len(state_returns) > 0 else 0.0
                avg_vol = float(np.mean(state_vol)) if len(state_vol) > 0 else 0.0

                if avg_ret > 0.01 and avg_vol < 0.03:
                    label = "牛市"
                elif avg_ret < -0.01 and avg_vol > 0.03:
                    label = "熊市"
                else:
                    label = "震荡"

                self._regime_characteristics[state] = {
                    "label": label,
                    "avg_20d_return": round(avg_ret, 6),
                    "avg_20d_volatility": round(avg_vol, 6),
                    "frequency": round(float(np.mean(states == state)), 4),
                }

            logger.info(
                "HMM trained: %d components, %d samples. Regimes: %s",
                self._n_components, len(features),
                {s: c["label"] for s, c in self._regime_characteristics.items()},
            )

            self._save_model()
            return True
        except Exception as e:
            logger.error("HMM training failed: %s", e)
            return False

    def predict_state(self, features: pd.DataFrame) -> HMMRegimeResult:
        if self._model is None:
            logger.warning("HMM model not trained, returning default")
            return HMMRegimeResult(
                current_regime=0,
                state_probabilities=[1.0, 0.0, 0.0][:self._n_components],
                regime_characteristics={},
                transition_matrix=np.eye(self._n_components),
                feature_names=self._feature_names,
            )

        try:
            latest_features = features.values[-1:]

            state_probs = self._model.predict_proba(latest_features)[0]
            current_regime = int(np.argmax(state_probs))

            return HMMRegimeResult(
                current_regime=current_regime,
                state_probabilities=[round(float(p), 4) for p in state_probs],
                regime_characteristics=dict(self._regime_characteristics),
                transition_matrix=self._model.transmat_.copy(),
                feature_names=list(self._feature_names),
            )
        except Exception as e:
            logger.error("HMM prediction failed: %s", e)
            return HMMRegimeResult(
                current_regime=0,
                state_probabilities=[1.0, 0.0, 0.0][:self._n_components],
                regime_characteristics={},
                transition_matrix=np.eye(self._n_components),
                feature_names=self._feature_names,
            )

    def _save_model(self) -> None:
        if self._model is None:
            return
        date_str = datetime.now().strftime("%Y%m%d")
        path = self._model_dir / f"hmm_model_{date_str}.pkl"
        try:
            with open(path, "wb") as f:
                pickle.dump({
                    "model": self._model,
                    "feature_names": self._feature_names,
                    "regime_characteristics": self._regime_characteristics,
                    "n_components": self._n_components,
                }, f)
            logger.info("HMM model saved to %s", path)
        except Exception as e:
            logger.warning("Failed to save HMM model: %s", e)

    def load_model(self, date_str: Optional[str] = None) -> bool:
        if date_str is None:
            models = sorted(self._model_dir.glob("hmm_model_*.pkl"))
            if not models:
                return False
            path = models[-1]
        else:
            path = self._model_dir / f"hmm_model_{date_str}.pkl"

        if not path.exists():
            logger.warning("Model file not found: %s", path)
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._model = data["model"]
            self._feature_names = data.get("feature_names", [])
            self._regime_characteristics = data.get("regime_characteristics", {})
            self._n_components = data.get("n_components", 3)
            logger.info("HMM model loaded from %s", path)
            return True
        except Exception as e:
            logger.error("Failed to load HMM model: %s", e)
            return False
