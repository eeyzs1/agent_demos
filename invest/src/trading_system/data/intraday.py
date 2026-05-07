import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class IntradayDataSource(ABC):
    @abstractmethod
    def fetch_intraday(self, symbol: str, period: str = "30", days_back: int = 20) -> pd.DataFrame:
        pass


class AKShareIntradaySource(IntradayDataSource):
    def fetch_intraday(self, symbol: str, period: str = "30", days_back: int = 20) -> pd.DataFrame:
        try:
            import akshare as ak

            df = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=period,
                adjust="",
            )

            if df.empty:
                return pd.DataFrame()

            df["日期"] = pd.to_datetime(df["日期"])
            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "换手率": "turnover",
            })

            df = df.set_index("date")
            df = df.sort_index()

            if days_back > 0:
                cutoff = df.index[-1] - pd.Timedelta(days=days_back)
                df = df[df.index >= cutoff]

            return df
        except Exception as e:
            logger.warning("Failed to fetch intraday data for %s: %s", symbol, e)
            return pd.DataFrame()


class VolumeProfile:
    def __init__(self, cache_dir: str = "./data/cache"):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._profile: Optional[list[float]] = None
        self._load()

    def get_profile(self, num_buckets: int = 8) -> list[float]:
        if self._profile is None or len(self._profile) == 0:
            return self._default_profile(num_buckets)

        if len(self._profile) != num_buckets:
            step = len(self._profile) / num_buckets
            result = []
            for i in range(num_buckets):
                start = int(i * step)
                end = int((i + 1) * step)
                result.append(sum(self._profile[start:end]) / (end - start))
            total = sum(result)
            return [v / total for v in result] if total > 0 else self._default_profile(num_buckets)

        return list(self._profile)

    def _load(self) -> None:
        file_path = self._cache_dir / "volume_profile.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profile = data.get("profile", [])
                logger.debug("Volume profile loaded")
            except Exception as e:
                logger.warning("Failed to load volume profile: %s", e)

    def save(self) -> None:
        if self._profile is None:
            return
        file_path = self._cache_dir / "volume_profile.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"profile": self._profile}, f)
        except Exception as e:
            logger.warning("Failed to save volume profile: %s", e)

    @staticmethod
    def _default_profile(num_buckets: int) -> list[float]:
        val = 1.0 / num_buckets
        return [val] * num_buckets


def decompose_overnight_intraday(daily_data: pd.DataFrame) -> pd.DataFrame:
    if "open" not in daily_data.columns or "close" not in daily_data.columns:
        logger.warning("Cannot decompose: missing open/close columns")
        return daily_data

    result = daily_data.copy()
    prev_close = result["close"].shift(1)

    result["overnight_return"] = (result["open"] - prev_close) / prev_close
    result["intraday_return"] = (result["close"] - result["open"]) / result["open"]
    result["daily_return"] = result["close"].pct_change()

    return result


def adjust_window_for_freq(window_days: int, freq: str) -> int:
    if freq == "daily":
        return window_days
    elif freq == "30min":
        return window_days * 8
    elif freq == "60min":
        return window_days * 4
    elif freq == "15min":
        return window_days * 16
    elif freq == "5min":
        return window_days * 48
    else:
        return window_days
