import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression

from trading_system.strategy.base import Signal, SignalType, StrategyBase

logger = logging.getLogger(__name__)


class PCAArbitrageStrategy(StrategyBase):
    def __init__(
        self,
        name: str = "pca_arbitrage",
        params: Optional[dict] = None,
        n_components: int = 5,
        entry_zscore: float = 2.0,
        exit_zscore: float = 0.5,
        lookback_residual: int = 20,
        retrain_days: int = 60,
        max_net_exposure: float = 0.05,
    ):
        super().__init__(name, params)
        self._n_components = n_components
        self._entry_zscore = entry_zscore
        self._exit_zscore = exit_zscore
        self._lookback_residual = lookback_residual
        self._retrain_days = retrain_days
        self._max_net_exposure = max_net_exposure
        self._pca: Optional[PCA] = None
        self._symbols: list[str] = []
        self._days_since_train: int = 999

    def fit_pca(self, returns_df: pd.DataFrame) -> PCA:
        standardized = (returns_df - returns_df.mean()) / returns_df.std()
        standardized = standardized.fillna(0)

        n = min(self._n_components, returns_df.shape[1], returns_df.shape[0])
        pca = PCA(n_components=n)
        pca.fit(standardized.values)
        self._pca = pca
        self._symbols = list(returns_df.columns)
        self._days_since_train = 0

        explained = sum(pca.explained_variance_ratio_[:n]) * 100
        logger.info(
            "PCA fitted: %d components, %.1f%% variance explained, %d symbols",
            n, explained, len(self._symbols),
        )
        return pca

    def generate_signals(self, data: pd.DataFrame) -> list[Signal]:
        return []

    def generate_arbitrage_signals(
        self,
        returns_df: pd.DataFrame,
    ) -> list[Signal]:
        if self._pca is None:
            logger.warning("PCA not fitted, returning no signals")
            return []

        if self._days_since_train >= self._retrain_days:
            self.fit_pca(returns_df.iloc[-252:])

        self._days_since_train += 1

        standardized = (returns_df - returns_df.mean()) / returns_df.std()
        standardized = standardized.fillna(0)

        scores = self._pca.transform(standardized.values)

        reg = LinearRegression()
        reg.fit(scores, standardized.values)

        predicted = reg.predict(scores)
        residuals = standardized.values - predicted

        residual_df = pd.DataFrame(residuals, index=returns_df.index, columns=returns_df.columns)

        cumulative_residuals = residual_df.rolling(self._lookback_residual).sum()

        signals = []
        latest_cum = cumulative_residuals.iloc[-1]
        residual_std = cumulative_residuals.std()

        buy_notional = 0.0
        sell_notional = 0.0

        for symbol in self._symbols:
            if symbol not in latest_cum.index:
                continue

            z = float(latest_cum[symbol] / residual_std[symbol]) if residual_std[symbol] > 0 else 0.0
            price = float(returns_df[symbol].iloc[-1]) if symbol in returns_df.columns else 0.0

            if z < -self._entry_zscore and price > 0:
                signals.append(Signal(
                    symbol=symbol, signal_type=SignalType.BUY,
                    price=price, strategy_name=self.name,
                    metadata={"zscore": round(z, 4), "side": "pca_arbitrage_buy"},
                ))
                buy_notional += abs(price)
            elif z > self._entry_zscore and price > 0:
                signals.append(Signal(
                    symbol=symbol, signal_type=SignalType.SELL,
                    price=price, strategy_name=self.name,
                    metadata={"zscore": round(z, 4), "side": "pca_arbitrage_sell"},
                ))
                sell_notional += abs(price)

        total = buy_notional + sell_notional
        if total > 0:
            net_exposure = abs(buy_notional - sell_notional) / total
            if net_exposure > self._max_net_exposure:
                logger.info(
                    "Net exposure %.2f%% exceeds limit %.1f%%, scaling signals",
                    net_exposure * 100, self._max_net_exposure * 100,
                )

        logger.info(
            "PCA arbitrage: %d BUY, %d SELL signals",
            sum(1 for s in signals if s.signal_type == SignalType.BUY),
            sum(1 for s in signals if s.signal_type == SignalType.SELL),
        )
        return signals

    def describe(self) -> dict:
        return {
            "name": self.name,
            "type": "pca_arbitrage",
            "n_components": self._n_components,
            "entry_zscore": self._entry_zscore,
            "exit_zscore": self._exit_zscore,
            "symbols_loaded": len(self._symbols) if self._pca else 0,
        }
