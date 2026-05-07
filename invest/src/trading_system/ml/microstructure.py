import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OrderBookSignalExtractor:
    def __init__(self, rolling_window: int = 20):
        self._rolling_window = rolling_window

    def extract(self, tick_data: pd.DataFrame) -> dict:
        if tick_data.empty:
            return self._empty_signal()

        if "price" not in tick_data.columns or "volume" not in tick_data.columns:
            logger.warning("Tick data missing required columns: price, volume")
            return self._empty_signal()

        classifications = self._lee_ready_classify(tick_data)

        buy_mask = classifications == 1
        sell_mask = classifications == -1

        buy_volume = float(tick_data.loc[buy_mask, "volume"].sum()) if buy_mask.any() else 0.0
        sell_volume = float(tick_data.loc[sell_mask, "volume"].sum()) if sell_mask.any() else 0.0
        total_volume = buy_volume + sell_volume

        volume_imbalance = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0.0

        buy_count = int(buy_mask.sum())
        sell_count = int(sell_mask.sum())

        avg_buy_size = buy_volume / buy_count if buy_count > 0 else 0.0
        avg_sell_size = sell_volume / sell_count if sell_count > 0 else 0.0
        total_avg_size = avg_buy_size + avg_sell_size

        trade_size_imbalance = (
            (avg_buy_size - avg_sell_size) / total_avg_size if total_avg_size > 0 else 0.0
        )

        if len(tick_data) >= 2:
            price_changes = tick_data["price"].diff()
            uptick_count = int((price_changes > 0).sum())
            tick_direction = uptick_count / max(len(tick_data) - 1, 1)
        else:
            tick_direction = 0.5

        composite_score = (volume_imbalance * 0.4 + trade_size_imbalance * 0.3 + (tick_direction - 0.5) * 2 * 0.3)
        composite_score = float(np.clip(composite_score, -1.0, 1.0))

        return {
            "volume_imbalance": round(volume_imbalance, 6),
            "trade_size_imbalance": round(trade_size_imbalance, 6),
            "tick_direction": round(tick_direction, 6),
            "composite_score": round(composite_score, 6),
            "buy_volume": round(buy_volume, 2),
            "sell_volume": round(sell_volume, 2),
            "timestamp": tick_data.index[-1].isoformat() if hasattr(tick_data.index[-1], "isoformat") else str(tick_data.index[-1]),
        }

    def aggregate_to_bar(self, tick_signals: list[dict]) -> dict:
        if not tick_signals:
            return self._empty_signal()

        keys = ["volume_imbalance", "trade_size_imbalance", "tick_direction", "composite_score"]
        aggregated = {}
        for key in keys:
            values = [s[key] for s in tick_signals if key in s]
            aggregated[key] = round(float(np.mean(values)), 6) if values else 0.0

        aggregated["n_ticks"] = len(tick_signals)
        return aggregated

    @staticmethod
    def _lee_ready_classify(tick_data: pd.DataFrame) -> np.ndarray:
        prices = tick_data["price"].values
        n = len(prices)

        classifications = np.zeros(n)

        if n < 2:
            return classifications

        mid_prices = np.zeros(n)
        if "bid" in tick_data.columns and "ask" in tick_data.columns:
            mid_prices = (tick_data["bid"].values + tick_data["ask"].values) / 2

        for i in range(n):
            price = prices[i]
            if i > 0:
                mid_ref = mid_prices[i] if mid_prices[i] > 0 else prices[i - 1]
                if price > mid_ref:
                    classifications[i] = 1
                elif price < mid_ref:
                    classifications[i] = -1
                else:
                    classifications[i] = classifications[i - 1] if i > 0 else 0
            else:
                classifications[i] = 0

        return classifications

    @staticmethod
    def _empty_signal() -> dict:
        return {
            "volume_imbalance": 0.0,
            "trade_size_imbalance": 0.0,
            "tick_direction": 0.5,
            "composite_score": 0.0,
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "timestamp": "",
        }
