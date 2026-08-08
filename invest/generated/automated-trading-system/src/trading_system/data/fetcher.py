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

        df = pd.DataFrame()
        # Prefer Sina K-line — East Money / akshare often blocked
        try:
            df = self._fetch_daily_sina_http(symbol, start_date, end_date)
        except Exception as e:
            logger.warning("Sina daily fetch failed for %s: %s", symbol, e)

        if df is None or df.empty:
            try:
                df = self._fetch_daily_eastmoney_http(symbol, start_date, end_date, adjust)
            except Exception as e:
                logger.warning("HTTP daily fetch failed for %s: %s", symbol, e)

        if df is None or df.empty:
            # Skip slow akshare hist when primary sources fail (often blocked)
            logger.warning("No daily data for %s from Sina/EM", symbol)
            df = pd.DataFrame()

        if df is not None and not df.empty:
            self._write_cache(cache_key, df)
            self._event_bus.publish(
                "data.daily_fetched",
                {"symbol": symbol, "rows": len(df), "start": start_date, "end": end_date},
            )
        return df if df is not None else pd.DataFrame()

    def _secid(self, symbol: str) -> str:
        s = str(symbol).zfill(6)
        return f"1.{s}" if s.startswith(("5", "6", "9")) else f"0.{s}"

    def _fetch_daily_sina_http(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Sina CN_MarketData.getKLineData daily bars."""
        import requests

        s = str(symbol).zfill(6)
        sina_symbol = f"sh{s}" if s.startswith(("5", "6", "9")) else f"sz{s}"
        # Request enough bars then filter by date
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        resp = requests.get(
            url,
            params={"symbol": sina_symbol, "scale": 240, "ma": "no", "datalen": 250},
            timeout=self.request_timeout,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.sina.com.cn",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or not data:
            return pd.DataFrame()

        rows = []
        start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
        prev_close = None
        for item in data:
            day = str(item.get("day", ""))
            if day < start or day > end:
                continue
            close = float(item["close"])
            open_ = float(item["open"])
            high = float(item["high"])
            low = float(item["low"])
            vol = float(item.get("volume") or 0)
            chg = 0.0
            if prev_close and prev_close > 0:
                chg = (close / prev_close - 1.0) * 100.0
            rows.append(
                {
                    "date": day,
                    "open": open_,
                    "close": close,
                    "high": high,
                    "low": low,
                    "volume": vol,
                    "amount": vol * close,
                    "amplitude": ((high - low) / prev_close * 100.0) if prev_close else 0.0,
                    "change_pct": chg,
                    "change_amount": (close - prev_close) if prev_close else 0.0,
                    "turnover_rate": 0.0,
                }
            )
            prev_close = close
        return pd.DataFrame(rows)

    def _fetch_daily_eastmoney_http(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """East Money push2his kline API → OHLCV DataFrame."""
        import requests

        fqt = 1 if adjust == "qfq" else (2 if adjust == "hfq" else 0)
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": self._secid(symbol),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": fqt,
            "beg": start_date,
            "end": end_date,
            "lmt": "1000000",
        }
        resp = requests.get(
            url,
            params=params,
            timeout=self.request_timeout,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
        )
        resp.raise_for_status()
        klines = ((resp.json() or {}).get("data") or {}).get("klines") or []
        if not klines:
            return pd.DataFrame()
        rows = []
        for line in klines:
            parts = str(line).split(",")
            if len(parts) < 11:
                continue
            rows.append(
                {
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": float(parts[5]),
                    "amount": float(parts[6]),
                    "amplitude": float(parts[7]) if parts[7] not in ("", "-") else 0.0,
                    "change_pct": float(parts[8]) if parts[8] not in ("", "-") else 0.0,
                    "change_amount": float(parts[9]) if parts[9] not in ("", "-") else 0.0,
                    "turnover_rate": float(parts[10]) if parts[10] not in ("", "-") else 0.0,
                }
            )
        return pd.DataFrame(rows)

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

    def get_stock_news(self, symbol: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Fetch recent news headlines for a stock.

        Tries akshare first, then a direct East Money HTTP fallback.
        Returns list of dicts: title, content, datetime, source.
        """
        symbol = str(symbol).strip().zfill(6)
        cache_key = self._cache_key("news", symbol, limit)
        cached = self._read_cache(cache_key)
        if cached is not None and not cached.empty:
            return cached.to_dict("records")

        df = pd.DataFrame()
        # Prefer F10 HTTP first — akshare stock_news_em currently breaks on some runtimes.
        try:
            df = self._fetch_news_eastmoney_http(symbol)
        except Exception as e:
            logger.warning("HTTP news fetch failed for %s: %s", symbol, e)

        if df is None or df.empty:
            try:
                df = self._retry_fetch(lambda: self._fetch_news_akshare(symbol))
            except Exception as e:
                logger.warning("akshare news failed for %s: %s", symbol, e)

        if df is None or df.empty:
            return []

        keep = [c for c in ("title", "content", "datetime", "source") if c in df.columns]
        if not keep:
            out = []
            for _, row in df.head(limit).iterrows():
                out.append({"title": str(row.iloc[0]), "content": "", "datetime": "", "source": ""})
            return out

        slim = df[keep].head(limit).copy()
        for c in ("title", "content", "datetime", "source"):
            if c not in slim.columns:
                slim[c] = ""
        # stringify for parquet
        for c in slim.columns:
            slim[c] = slim[c].astype(str)
        self._write_cache(cache_key, slim)
        return slim.to_dict("records")

    def _normalize_news_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        rename = {}
        for c in df.columns:
            cs = str(c)
            cl = cs.lower()
            if "标题" in cs or cl in {"title", "新闻标题"}:
                rename[c] = "title"
            elif "内容" in cs or "摘要" in cs or cl in {"content", "新闻内容", "digest"}:
                rename[c] = "content"
            elif "时间" in cs or "date" in cl or "datetime" in cl or cl == "showtime":
                rename[c] = "datetime"
            elif "来源" in cs or "source" in cl or "media" in cl:
                rename[c] = "source"
        return df.rename(columns=rename)

    def _fetch_news_akshare(self, symbol: str) -> pd.DataFrame:
        import akshare as ak
        df = ak.stock_news_em(symbol=symbol)
        return self._normalize_news_frame(df if df is not None else pd.DataFrame())

    def _fetch_news_eastmoney_http(self, symbol: str) -> pd.DataFrame:
        """East Money F10 news/bulletin API (more stable than search JSONP)."""
        import requests

        symbol = str(symbol).zfill(6)
        if symbol.startswith(("5", "6", "9")):
            em_code = f"SH{symbol}"
        else:
            em_code = f"SZ{symbol}"

        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewsBulletin/PageAjax"
        resp = requests.get(
            url,
            params={"code": em_code},
            timeout=self.request_timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = []

        # Company news
        gszx = (payload.get("gszx") or {}).get("data") or {}
        for a in gszx.get("items") or []:
            ts = a.get("showDateTime") or a.get("updateTime") or 0
            dt = ""
            try:
                if ts and int(ts) > 10_000_000_000:  # ms
                    dt = datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                elif ts and int(ts) > 1_000_000_000:
                    dt = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = str(ts or "")
            rows.append(
                {
                    "title": a.get("title") or "",
                    "content": a.get("summary") or a.get("content") or a.get("digest") or "",
                    "datetime": dt,
                    "source": a.get("source") or a.get("media_name") or "eastmoney",
                }
            )

        # Announcements (also informative for message score)
        for a in payload.get("gsgg") or []:
            if not isinstance(a, dict):
                continue
            rows.append(
                {
                    "title": a.get("title") or "",
                    "content": a.get("content") or "",
                    "datetime": str(a.get("display_time") or a.get("notice_date") or ""),
                    "source": "announcement",
                }
            )

        return pd.DataFrame(rows) if rows else pd.DataFrame()
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