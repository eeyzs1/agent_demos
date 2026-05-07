import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from trading_system.data.capital_flow import NorthFlowData
from trading_system.data.fundamental import FundamentalData
from trading_system.data.sources import (
    AKShareSource,
    DataSource,
    YFinanceSource,
)
from trading_system.data.validator import DataValidator

logger = logging.getLogger(__name__)

CACHE_TTL_DAILY = timedelta(hours=24)
CACHE_TTL_REALTIME = timedelta(minutes=5)
CACHE_TTL_FINANCIAL = timedelta(days=7)
CACHE_TTL_NORTH_FLOW = timedelta(days=1)
CACHE_TTL_DRAGON_TIGER = timedelta(days=1)


class DataStore:
    def __init__(
        self, cache_dir: str = "./data/cache", db_url: str = "sqlite:///./data/trading.db"
    ):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_url = db_url
        self._sources: dict[str, DataSource] = {
            "akshare": AKShareSource(),
            "yfinance": YFinanceSource(),
        }
        self._validator = DataValidator()

    def get_source(self, name: str) -> DataSource:
        if name not in self._sources:
            raise ValueError(
                f"Unknown data source: {name}. Available: {list(self._sources.keys())}"
            )
        return self._sources[name]

    def fetch_daily(
        self,
        symbol: str,
        source: str = "akshare",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        cache_key = f"daily_{source}_{symbol}_{start_date}_{end_date}"
        if use_cache:
            cached, meta = self._load_cache_with_meta(cache_key)
            if cached is not None and not self._is_expired(meta, CACHE_TTL_DAILY):
                logger.debug("Cache hit for %s", cache_key)
                return cached

            if cached is not None and start_date is None:
                last_date = self._get_last_date(cached)
                if last_date is not None:
                    incremental_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    ds = self.get_source(source)
                    new_df = ds.fetch_daily(symbol, incremental_start, end_date)
                    if not new_df.empty:
                        combined = pd.concat([cached, new_df]).drop_duplicates()
                        combined = combined[~combined.index.duplicated(keep="last")]
                        combined.sort_index(inplace=True)
                        self._save_cache_with_meta(cache_key, combined)
                        return combined
                    self._save_cache_with_meta(cache_key, cached)
                    return cached

        ds = self.get_source(source)
        df = ds.fetch_daily(symbol, start_date, end_date)

        if use_cache and not df.empty:
            self._save_cache_with_meta(cache_key, df)

        return df

    def fetch_realtime(self, symbol: str, source: str = "akshare") -> dict:
        ds = self.get_source(source)
        data = ds.fetch_realtime(symbol)
        validation = self._validator.validate_realtime(data, symbol=symbol)
        if not self._validator.is_safe_for_trading(validation):
            for issue in validation.issues:
                if issue["severity"] in ("critical", "error"):
                    logger.warning(
                        "Data validation failed for %s: %s", symbol, issue["message"]
                    )
        return data

    def get_symbol_list(self, market: str = "A", source: str = "akshare") -> pd.DataFrame:
        ds = self.get_source(source)
        return ds.get_symbol_list(market)

    def fetch_financial(self, symbol: str, source: str = "akshare") -> FundamentalData:
        cache_key = f"financial_{source}_{symbol}"
        cached, meta = self._load_cache_with_meta(cache_key)
        if cached is not None and not self._is_expired(meta, CACHE_TTL_FINANCIAL):
            logger.debug("Cache hit for %s", cache_key)
            data_dict = cached.iloc[0].to_dict() if len(cached) > 0 else {}
            if data_dict:
                return FundamentalData.from_dict(data_dict)

        ds = self.get_source(source)
        if not hasattr(ds, "fetch_financial"):
            raise ValueError(f"Data source {source} does not support fetch_financial")

        result = ds.fetch_financial(symbol)

        if result:
            df = pd.DataFrame([result])
            self._save_cache_with_meta(cache_key, df)
            return FundamentalData.from_dict(result)

        return FundamentalData(symbol=symbol)

    def fetch_north_flow(self, source: str = "akshare") -> list[NorthFlowData]:
        cache_key = f"north_flow_{source}"
        cached, meta = self._load_cache_with_meta(cache_key)
        if cached is not None and not self._is_expired(meta, CACHE_TTL_NORTH_FLOW):
            logger.debug("Cache hit for %s", cache_key)
            return [NorthFlowData.from_dict(row.to_dict()) for _, row in cached.iterrows()]

        ds = self.get_source(source)
        if not hasattr(ds, "fetch_north_flow"):
            raise ValueError(f"Data source {source} does not support fetch_north_flow")

        result = ds.fetch_north_flow()
        if result:
            df = pd.DataFrame(result)
            self._save_cache_with_meta(cache_key, df)
            return [NorthFlowData.from_dict(r) for r in result]

        return []

    def fetch_dragon_tiger(self, date: str = "", source: str = "akshare") -> list[dict]:
        cache_key = f"dragon_tiger_{source}_{date}"
        cached, meta = self._load_cache_with_meta(cache_key)
        if cached is not None and not self._is_expired(meta, CACHE_TTL_DRAGON_TIGER):
            logger.debug("Cache hit for %s", cache_key)
            return cached.to_dict("records")

        ds = self.get_source(source)
        if not hasattr(ds, "fetch_dragon_tiger"):
            raise ValueError(f"Data source {source} does not support fetch_dragon_tiger")

        result = ds.fetch_dragon_tiger(date)
        if result:
            df = pd.DataFrame(result)
            self._save_cache_with_meta(cache_key, df)
            return result

        return []

    @staticmethod
    def _get_last_date(df: pd.DataFrame) -> Optional[datetime]:
        if df.empty:
            return None
        last_idx = df.index[-1]
        if isinstance(last_idx, pd.Timestamp):
            return last_idx.to_pydatetime()
        try:
            return pd.Timestamp(last_idx).to_pydatetime()
        except Exception:
            return None

    @staticmethod
    def _is_expired(meta: dict, ttl: timedelta) -> bool:
        if not meta or "saved_at" not in meta:
            return True
        try:
            saved = datetime.fromisoformat(meta["saved_at"])
            return datetime.now() - saved > ttl
        except Exception:
            return True

    def _load_cache_with_meta(self, key: str) -> tuple[Optional[pd.DataFrame], dict]:
        cache_file = self._cache_dir / f"{key}.parquet"
        meta_file = self._cache_dir / f"{key}.meta.json"
        if cache_file.exists():
            try:
                df = pd.read_parquet(cache_file)
                meta = {}
                if meta_file.exists():
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                return df, meta
            except Exception as e:
                logger.warning("Cache read failed for %s: %s", key, e)
                return None, {}
        return None, {}

    def _save_cache_with_meta(self, key: str, df: pd.DataFrame) -> None:
        cache_file = self._cache_dir / f"{key}.parquet"
        meta_file = self._cache_dir / f"{key}.meta.json"
        try:
            df.to_parquet(cache_file)
            meta = {
                "saved_at": datetime.now().isoformat(),
                "rows": len(df),
                "columns": list(df.columns),
            }
            last_date = self._get_last_date(df)
            if last_date:
                meta["last_date"] = last_date.isoformat()
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Cache write failed for %s: %s", key, e)

    def _load_cache(self, key: str) -> Optional[pd.DataFrame]:
        df, _ = self._load_cache_with_meta(key)
        return df

    def _save_cache(self, key: str, df: pd.DataFrame) -> None:
        self._save_cache_with_meta(key, df)

    def fetch_daily_volume(self, symbol: str, days: int = 20, source: str = "akshare") -> float:
        cache_key = f"daily_{source}_{symbol}_volume_{days}"
        cached, meta = self._load_cache_with_meta(cache_key)
        if cached is not None and not self._is_expired(meta, CACHE_TTL_DAILY):
            logger.debug("Volume cache hit for %s", cache_key)
            if "volume" in cached.columns and not cached.empty:
                return float(cached["volume"].tail(days).mean())

        df = self.fetch_daily(symbol, source=source, use_cache=True)
        if df.empty or "volume" not in df.columns:
            logger.warning("No volume data for %s, returning 0", symbol)
            return 0.0

        avg_volume = float(df["volume"].tail(days).mean())
        self._save_cache_with_meta(cache_key, df.tail(days))
        return avg_volume

    def fetch_intraday(
        self,
        symbol: str,
        period: str = "30",
        days_back: int = 20,
        source: str = "akshare",
    ) -> "pd.DataFrame":
        import pandas as pd

        cache_key = f"intraday_{source}_{symbol}_{period}_{days_back}"
        cached, meta = self._load_cache_with_meta(cache_key)
        cache_ttl = timedelta(minutes=5)
        if cached is not None and not self._is_expired(meta, cache_ttl):
            logger.debug("Intraday cache hit for %s", cache_key)
            return cached

        ds = self.get_source(source)
        if hasattr(ds, "fetch_intraday"):
            df = ds.fetch_intraday(symbol, period=period, days_back=days_back)
        else:
            logger.warning("Source %s does not support intraday data", source)
            df = pd.DataFrame()

        if not df.empty:
            self._save_cache_with_meta(cache_key, df)

        return df

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        count = 0
        for f in list(self._cache_dir.glob("*.parquet")) + list(
            self._cache_dir.glob("*.meta.json")
        ):
            if older_than_days is None:
                f.unlink()
                count += 1
            else:
                age = (datetime.now().timestamp() - f.stat().st_mtime) / 86400
                if age > older_than_days:
                    f.unlink()
                    count += 1
        return count
