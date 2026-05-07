import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint

from trading_system.strategy.base import Signal, SignalType, StrategyBase

logger = logging.getLogger(__name__)


@dataclass
class CointegratedPair:
    symbol_y: str
    symbol_x: str
    hedge_ratio: float
    spread_mean: float
    spread_std: float
    p_value: float
    adf_t_stat: float
    correlation: float
    last_tested: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True
    performance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol_y": self.symbol_y,
            "symbol_x": self.symbol_x,
            "hedge_ratio": self.hedge_ratio,
            "spread_mean": self.spread_mean,
            "spread_std": self.spread_std,
            "p_value": self.p_value,
            "adf_t_stat": self.adf_t_stat,
            "correlation": self.correlation,
            "last_tested": self.last_tested,
            "is_active": self.is_active,
            "performance": self.performance,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CointegratedPair":
        return cls(
            symbol_y=d["symbol_y"],
            symbol_x=d["symbol_x"],
            hedge_ratio=d["hedge_ratio"],
            spread_mean=d["spread_mean"],
            spread_std=d["spread_std"],
            p_value=d["p_value"],
            adf_t_stat=d["adf_t_stat"],
            correlation=d["correlation"],
            last_tested=d.get("last_tested", datetime.now().isoformat()),
            is_active=d.get("is_active", True),
            performance=d.get("performance", {}),
        )

    @property
    def pair_id(self) -> str:
        return f"{self.symbol_y}-{self.symbol_x}"


class PairsRegistry:
    def __init__(self, data_dir: str = "./data/pairs"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._pairs: dict[str, CointegratedPair] = {}
        self._load()

    def _load(self) -> None:
        file_path = self._data_dir / "active_pairs.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    pair = CointegratedPair.from_dict(item)
                    self._pairs[pair.pair_id] = pair
                logger.info("Loaded %d pairs from registry", len(self._pairs))
            except Exception as e:
                logger.warning("Failed to load pairs registry: %s", e)

    def save(self) -> None:
        file_path = self._data_dir / "active_pairs.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([p.to_dict() for p in self._pairs.values()], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save pairs registry: %s", e)

    def add_pair(self, pair: CointegratedPair) -> None:
        self._pairs[pair.pair_id] = pair
        self.save()

    def remove_pair(self, pair_id: str) -> None:
        self._pairs.pop(pair_id, None)
        self.save()

    def get_active_pairs(self) -> list[CointegratedPair]:
        return [p for p in self._pairs.values() if p.is_active]

    def get_pair(self, pair_id: str) -> Optional[CointegratedPair]:
        return self._pairs.get(pair_id)

    def deactivate_expired(self, max_days: int = 20) -> int:
        count = 0
        cutoff = datetime.now() - timedelta(days=max_days)
        for pair_id, pair in list(self._pairs.items()):
            try:
                tested = datetime.fromisoformat(pair.last_tested)
                if tested < cutoff:
                    pair.is_active = False
                    count += 1
            except (ValueError, TypeError):
                pass
        if count > 0:
            self.save()
        return count


class PairsTradingStrategy(StrategyBase):
    def __init__(
        self,
        name: str = "pairs_trading",
        params: Optional[dict] = None,
        registry: Optional[PairsRegistry] = None,
        min_correlation: float = 0.7,
        p_value_threshold: float = 0.05,
        adf_threshold: float = -3.0,
        entry_zscore: float = 2.0,
        exit_zscore: float = 0.5,
        lookback_days: int = 60,
        retest_days: int = 20,
        use_kalman: bool = False,
        kalman_filter=None,
    ):
        super().__init__(name, params)
        self._min_correlation = min_correlation
        self._p_value_threshold = p_value_threshold
        self._adf_threshold = adf_threshold
        self._entry_zscore = entry_zscore
        self._exit_zscore = exit_zscore
        self._lookback_days = lookback_days
        self._retest_days = retest_days
        self._use_kalman = use_kalman
        self._kalman_filter = kalman_filter
        self._registry = registry or PairsRegistry()
        self._last_retest: dict[str, datetime] = {}

    def discover_pairs(
        self,
        price_data: dict[str, pd.DataFrame],
        symbols: Optional[list[str]] = None,
    ) -> list[CointegratedPair]:
        if symbols is None:
            symbols = list(price_data.keys())

        close_prices = {}
        for sym in symbols:
            if sym in price_data and "close" in price_data[sym].columns:
                close_prices[sym] = price_data[sym]["close"]

        pairs = []
        n = len(symbols)
        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = symbols[i], symbols[j]
                if s1 not in close_prices or s2 not in close_prices:
                    continue

                common_idx = close_prices[s1].index.intersection(close_prices[s2].index)
                if len(common_idx) < self._lookback_days:
                    continue

                p1 = close_prices[s1].loc[common_idx]
                p2 = close_prices[s2].loc[common_idx]

                corr = p1.corr(p2)
                if abs(corr) < self._min_correlation:
                    continue

                try:
                    coint_result = coint(p1, p2)
                    p_value = coint_result[1]
                    if p_value >= self._p_value_threshold:
                        continue

                    hedge_ratio = np.polyfit(p2.values, p1.values, 1)[0]
                    spread = p1.values - hedge_ratio * p2.values

                    adf_result = adfuller(spread, maxlag=int(len(spread) ** 0.25))
                    adf_t_stat = adf_result[0]

                    if adf_t_stat > self._adf_threshold:
                        continue

                    pair = CointegratedPair(
                        symbol_y=s1,
                        symbol_x=s2,
                        hedge_ratio=round(float(hedge_ratio), 6),
                        spread_mean=round(float(np.mean(spread)), 6),
                        spread_std=round(float(np.std(spread)), 6),
                        p_value=round(float(p_value), 6),
                        adf_t_stat=round(float(adf_t_stat), 4),
                        correlation=round(float(corr), 4),
                    )
                    pairs.append(pair)
                    logger.info(
                        "Discovered pair: %s-%s hedge=%.4f adf=%.2f",
                        s1, s2, hedge_ratio, adf_t_stat,
                    )
                except Exception as e:
                    logger.debug("Failed to test pair %s-%s: %s", s1, s2, e)

        logger.info("Discovered %d cointegrated pairs from %d symbols", len(pairs), n)
        return pairs

    def generate_signals(self, data: pd.DataFrame) -> list[Signal]:
        return []

    def generate_pair_signals(
        self,
        price_data: dict[str, pd.DataFrame],
    ) -> list[Signal]:
        signals = []
        now = datetime.now()

        for pair in self._registry.get_active_pairs():
            pair_id = pair.pair_id
            if pair_id in self._last_retest:
                days_since = (now - self._last_retest[pair_id]).days
                if days_since >= self._retest_days:
                    self._retest_pair(pair, price_data)
                    self._last_retest[pair_id] = now
            else:
                self._last_retest[pair_id] = now

            if not pair.is_active:
                continue

            y_data = price_data.get(pair.symbol_y)
            x_data = price_data.get(pair.symbol_x)
            if y_data is None or x_data is None:
                continue

            y_close = y_data["close"].values
            x_close = x_data["close"].values
            min_len = min(len(y_close), len(x_close))
            if min_len < self._lookback_days:
                continue

            y_close = y_close[-min_len:]
            x_close = x_close[-min_len:]

            if self._use_kalman and self._kalman_filter:
                hedge_ratio = self._get_kalman_hedge(y_close, x_close)
            else:
                hedge_ratio = pair.hedge_ratio

            spread = y_close - hedge_ratio * x_close
            spread_mean = float(np.mean(spread[-self._lookback_days:]))
            spread_std = float(np.std(spread[-self._lookback_days:]))

            if spread_std <= 0:
                continue

            current_spread = spread[-1]
            zscore = (current_spread - spread_mean) / spread_std

            if zscore > self._entry_zscore:
                signals.append(Signal(
                    symbol=pair.symbol_y,
                    signal_type=SignalType.SELL,
                    price=float(y_close[-1]),
                    strategy_name=f"pairs_{pair.pair_id}",
                    metadata={"pair_id": pair.pair_id, "zscore": round(zscore, 4), "side": "short_spread"},
                ))
                signals.append(Signal(
                    symbol=pair.symbol_x,
                    signal_type=SignalType.BUY,
                    price=float(x_close[-1]),
                    strategy_name=f"pairs_{pair.pair_id}",
                    metadata={"pair_id": pair.pair_id, "zscore": round(zscore, 4), "side": "long_spread"},
                ))
            elif zscore < -self._entry_zscore:
                signals.append(Signal(
                    symbol=pair.symbol_y,
                    signal_type=SignalType.BUY,
                    price=float(y_close[-1]),
                    strategy_name=f"pairs_{pair.pair_id}",
                    metadata={"pair_id": pair.pair_id, "zscore": round(zscore, 4), "side": "long_spread"},
                ))
                signals.append(Signal(
                    symbol=pair.symbol_x,
                    signal_type=SignalType.SELL,
                    price=float(x_close[-1]),
                    strategy_name=f"pairs_{pair.pair_id}",
                    metadata={"pair_id": pair.pair_id, "zscore": round(zscore, 4), "side": "short_spread"},
                ))

        return signals

    def _retest_pair(self, pair: CointegratedPair, price_data: dict[str, pd.DataFrame]) -> None:
        y_data = price_data.get(pair.symbol_y)
        x_data = price_data.get(pair.symbol_x)
        if y_data is None or x_data is None:
            pair.is_active = False
            return

        y_close = y_data["close"].values
        x_close = x_data["close"].values

        try:
            coint_result = coint(y_close, x_close)
            p_value = coint_result[1]
            if p_value >= self._p_value_threshold:
                pair.is_active = False
                logger.info("Pair %s deactivated: cointegration p=%.4f", pair.pair_id, p_value)
                return

            hedge_ratio = np.polyfit(x_close, y_close, 1)[0]
            spread = y_close - hedge_ratio * x_close
            adf_result = adfuller(spread, maxlag=int(len(spread) ** 0.25))
            adf_t_stat = adf_result[0]

            pair.hedge_ratio = round(float(hedge_ratio), 6)
            pair.spread_mean = round(float(np.mean(spread)), 6)
            pair.spread_std = round(float(np.std(spread)), 6)
            pair.p_value = round(float(p_value), 6)
            pair.adf_t_stat = round(float(adf_t_stat), 4)
            pair.last_tested = datetime.now().isoformat()
            pair.is_active = adf_t_stat <= self._adf_threshold

            logger.info("Retested pair %s: adf=%.2f active=%s", pair.pair_id, adf_t_stat, pair.is_active)
        except Exception as e:
            logger.warning("Failed to retest pair %s: %s", pair.pair_id, e)

    def _get_kalman_hedge(self, y_close: np.ndarray, x_close: np.ndarray) -> float:
        if self._kalman_filter is None:
            return self._registry.get_pair("") or 1.0

        for i in range(len(y_close)):
            self._kalman_filter.update(float(y_close[i]), float(x_close[i]))

        return float(self._kalman_filter.beta)

    def describe(self) -> dict:
        return {
            "name": self.name,
            "type": "pairs_trading",
            "min_correlation": self._min_correlation,
            "entry_zscore": self._entry_zscore,
            "exit_zscore": self._exit_zscore,
            "active_pairs": len(self._registry.get_active_pairs()),
        }
