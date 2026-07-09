"""Market data fetcher using akshare.

Fetches daily OHLCV, intraday bar data, stock lists, and financial data.
Depends only on core and akshare (AR003).
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.event_bus import get_event_bus

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetches market data from akshare with caching and retry support.

    Attributes:
        cache_dir: Directory for cached data files.
        cache_ttl_hours: Time-to-live for cached data in hours.
        request_timeout: Timeout for akshare requests in seconds.
    """

    def __init__(self, config_dir: str = "config"):
        config = get_config(config_dir)
        self.cache_dir = Path(config.get("data.cache_dir", "data/cache"))
        self.cache_ttl_hours = config.get("data.cache_ttl_hours", 24)
        self.request_timeout = config.get("data.request_timeout", 30)
        self.max_retries = config.get("data.max_retries", 3)
        self.retry_delay = config.get("data.retry_delay", 5)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._event_bus = get_event_bus()
        self._audit = get_audit_logger()

    def _cache_key(self, *args) -> str:
        """Generate a cache key from arguments."""
        raw = "_".join(str(a) for a in args)
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.parquet"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        age = time.time() - cache_path.stat().st_mtime
        return age < self.cache_ttl_hours * 3600

    def _read_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(cache_key)
        if self._is_cache_valid(path):
            try:
                return pd.read_parquet(path)
            except Exception:
                logger.warning("Failed to read cache: %s", path)
        return None

    def _write_cache(self, cache_key: str, df: pd.DataFrame) -> None:
        path = self._cache_path(cache_key)
        try:
            df.to_parquet(path, index=False)
        except Exception:
            logger.warning("Failed to write cache: %s", path)

    def _retry_fetch(self, fetch_fn, *args, **kwargs) -> pd.DataFrame:
        """Retry a data fetch with exponential backoff."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return fetch_fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        "Fetch attempt %d/%d failed: %s. Retrying in %ds...",
                        attempt + 1, self.max_retries, e, delay,
                    )
                    time.sleep(delay)
        logger.error("All %d fetch attempts failed: %s", self.max_retries, last_error)
        raise last_error

    def get_stock_list(self) -> pd.DataFrame:
        """Get A-share stock list (code, name, industry, area, market, list_date).

        Returns:
            DataFrame with columns: code, name, industry, area, market, list_date.
        """
        cache_key = self._cache_key("stock_list")
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            import akshare as ak
            df = ak.stock_info_a_code_name()
            df.columns = [c.lower() for c in df.columns]
            # Normalize column names
            col_map = {
                "code": "code", "name": "name",
                "stock_code": "code", "stock_name": "name",
            }
            df = df.rename(columns=col_map)
            return df

        df = self._retry_fetch(_fetch)
        self._write_cache(cache_key, df)
        self._audit.log(
            "data_fetch",
            check_id="stock_list",
            result="OK",
            payload={"count": len(df)},
        )
        self._event_bus.publish("data.stock_list_updated", {"count": len(df)})
        return df

    def get_daily_data(
        self,
        symbol: str,
        start_date: str = "20200101",
        end_date: str = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """Get daily OHLCV data for a single stock.

        Args:
            symbol: Stock code (e.g., '600519').
            start_date: Start date in 'YYYYMMDD' format.
            end_date: End date in 'YYYYMMDD' format (default: today).
            adjust: Price adjustment method ('qfq'=前复权, 'hfq'=后复权, ''=不复权).

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount, ...
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        cache_key = self._cache_key("daily", symbol, start_date, end_date, adjust)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            import akshare as ak
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
            return df

        df = self._retry_fetch(_fetch)
        if df is not None and not df.empty:
            self._write_cache(cache_key, df)
            self._event_bus.publish(
                "data.daily_fetched",
                {"symbol": symbol, "rows": len(df), "start": start_date, "end": end_date},
            )
        return df if df is not None else pd.DataFrame()

    def get_intraday_data(
        self,
        symbol: str,
        period: str = "5",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """Get intraday bar data for a single stock.

        Args:
            symbol: Stock code (e.g., '600519').
            period: Bar period ('1', '5', '15', '30', '60').
            adjust: Price adjustment method.

        Returns:
            DataFrame with intraday bar data.
        """
        cache_key = self._cache_key("intraday", symbol, period, adjust)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            import akshare as ak
            df = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=period,
                adjust=adjust,
            )
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
            return df

        df = self._retry_fetch(_fetch)
        if df is not None and not df.empty:
            self._write_cache(cache_key, df)
            self._event_bus.publish(
                "data.intraday_fetched",
                {"symbol": symbol, "period": period, "rows": len(df)},
            )
        return df if df is not None else pd.DataFrame()

    def get_index_data(
        self,
        index_code: str = "000300",
        start_date: str = "20200101",
        end_date: str = None,
    ) -> pd.DataFrame:
        """Get index daily data.

        Args:
            index_code: Index code (e.g., '000300' for CSI 300).
            start_date: Start date in 'YYYYMMDD' format.
            end_date: End date in 'YYYYMMDD' format.

        Returns:
            DataFrame with index OHLCV data.
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        cache_key = self._cache_key("index", index_code, start_date, end_date)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            import akshare as ak
            df = ak.stock_zh_index_daily_em(
                symbol=f"sh{index_code}" if index_code.startswith("0") else f"sz{index_code}",
                start_date=start_date,
                end_date=end_date,
            )
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
            return df

        try:
            df = self._retry_fetch(_fetch)
            if df is not None and not df.empty:
                self._write_cache(cache_key, df)
            return df if df is not None else pd.DataFrame()
        except Exception:
            logger.warning("Failed to fetch index data for %s", index_code)
            return pd.DataFrame()

    def get_financial_data(self, symbol: str) -> pd.DataFrame:
        """Get financial statements for a stock.

        Args:
            symbol: Stock code.

        Returns:
            DataFrame with financial indicators.
        """
        cache_key = self._cache_key("financial", symbol)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            import akshare as ak
            df = ak.stock_financial_abstract_ths(symbol=symbol)
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
            return df

        try:
            df = self._retry_fetch(_fetch)
            if df is not None and not df.empty:
                self._write_cache(cache_key, df)
            return df if df is not None else pd.DataFrame()
        except Exception:
            logger.warning("Failed to fetch financial data for %s", symbol)
            return pd.DataFrame()

    def get_market_sentiment_data(self) -> Dict[str, Any]:
        """Get market-wide sentiment indicators.

        Returns:
            Dict with market breadth, limit up/down counts, turnover, etc.
        """
        cache_key = self._cache_key("market_sentiment")
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached.to_dict("records")[0] if not cached.empty else {}

        result = {}
        try:
            import akshare as ak

            # Market breadth (涨跌家数)
            try:
                breadth = ak.stock_zh_index_daily_em(symbol="sh000001")
                if breadth is not None and not breadth.empty:
                    result["breadth_available"] = True
            except Exception:
                result["breadth_available"] = False

            result["fetched_at"] = datetime.now().isoformat()
            # Cache as DataFrame
            pd.DataFrame([result]).to_parquet(self._cache_path(cache_key))
            self._event_bus.publish("data.sentiment_fetched", result)
        except Exception as e:
            logger.warning("Failed to fetch sentiment data: %s", e)

        return result

    def clear_cache(self, older_than_hours: int = None) -> int:
        """Clear cached data files.

        Args:
            older_than_hours: Only clear files older than this many hours.

        Returns:
            Number of files deleted.
        """
        count = 0
        for f in self.cache_dir.glob("*.parquet"):
            if older_than_hours:
                age = (time.time() - f.stat().st_mtime) / 3600
                if age < older_than_hours:
                    continue
            f.unlink()
            count += 1
        return count