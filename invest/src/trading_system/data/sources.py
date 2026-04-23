from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import pandas as pd


class DataSource(ABC):
    @abstractmethod
    def fetch_daily(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def fetch_realtime(self, symbol: str) -> dict:
        pass

    @abstractmethod
    def get_symbol_list(self, market: str = "A") -> pd.DataFrame:
        pass

    @staticmethod
    def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "pct_change",
            "Date": "date",
            "Open": "open",
            "Close": "close",
            "High": "high",
            "Low": "low",
            "Volume": "volume",
        }
        df = df.rename(columns=column_map)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_index()
        return df


class AKShareSource(DataSource):
    def fetch_daily(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        import akshare as ak

        start = start_date or "20200101"
        end = end_date or datetime.now().strftime("%Y%m%d")
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            return self.normalize_columns(df)
        except Exception as e:
            raise DataFetchError(f"AKShare fetch failed for {symbol}: {e}") from e

    def fetch_realtime(self, symbol: str) -> dict:
        import akshare as ak

        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == symbol]
            if row.empty:
                raise DataFetchError(f"Symbol {symbol} not found in realtime data")
            row = row.iloc[0]
            return {
                "symbol": symbol,
                "name": row.get("名称", ""),
                "price": float(row.get("最新价", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
                "volume": float(row.get("成交量", 0)),
                "amount": float(row.get("成交额", 0)),
                "high": float(row.get("最高", 0)),
                "low": float(row.get("最低", 0)),
                "open": float(row.get("今开", 0)),
            }
        except Exception as e:
            raise DataFetchError(f"AKShare realtime fetch failed for {symbol}: {e}") from e

    def get_symbol_list(self, market: str = "A") -> pd.DataFrame:
        import akshare as ak

        try:
            if market == "A":
                df = ak.stock_zh_a_spot_em()
                return df[["代码", "名称"]].rename(columns={"代码": "symbol", "名称": "name"})
            raise DataFetchError(f"Market {market} not supported by AKShare source")
        except Exception as e:
            raise DataFetchError(f"AKShare symbol list fetch failed: {e}") from e

    def fetch_financial(self, symbol: str) -> dict:
        import akshare as ak

        try:
            result = {
                "symbol": symbol,
                "pe_ttm": None,
                "pb": None,
                "roe": None,
                "revenue_growth": None,
                "net_profit_growth": None,
                "gross_margin": None,
                "net_margin": None,
                "debt_ratio": None,
                "current_ratio": None,
                "eps": None,
                "bps": None,
                "report_date": None,
            }

            try:
                df_indicator = ak.stock_a_indicator_lg(symbol=symbol)
                if not df_indicator.empty:
                    latest = df_indicator.iloc[-1]
                    result["pe_ttm"] = self._safe_float(latest.get("pe_ttm"))
                    result["pb"] = self._safe_float(latest.get("pb"))
                    if "date" in df_indicator.columns:
                        result["report_date"] = str(latest.get("date", ""))
            except Exception:
                pass

            try:
                df_fin = ak.stock_financial_analysis_indicator(symbol=symbol)
                if not df_fin.empty:
                    latest = df_fin.iloc[0]
                    result["roe"] = self._safe_float(latest.get("净资产收益率(%)"))
                    result["gross_margin"] = self._safe_float(latest.get("销售毛利率(%)"))
                    result["net_margin"] = self._safe_float(latest.get("销售净利率(%)"))
                    result["debt_ratio"] = self._safe_float(latest.get("资产负债率(%)"))
                    result["current_ratio"] = self._safe_float(latest.get("流动比率"))
                    if not result["report_date"]:
                        result["report_date"] = str(latest.get("日期", ""))
            except Exception:
                pass

            try:
                df_growth = ak.stock_financial_growth_analysis_indicator(symbol=symbol)
                if not df_growth.empty:
                    latest = df_growth.iloc[0]
                    result["revenue_growth"] = self._safe_float(
                        latest.get("营业收入同比增长率(%)")
                    )
                    result["net_profit_growth"] = self._safe_float(
                        latest.get("净利润同比增长率(%)")
                    )
            except Exception:
                pass

            return result
        except Exception as e:
            raise DataFetchError(f"AKShare financial fetch failed for {symbol}: {e}") from e

    def fetch_north_flow(self) -> list[dict]:
        import akshare as ak

        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
            if df.empty:
                return []
            results = []
            for _, row in df.iterrows():
                results.append({
                    "date": str(row.get("日期", "")),
                    "sh_net_inflow": self._safe_float(row.get("沪股通净流入")),
                    "sz_net_inflow": self._safe_float(row.get("深股通净流入")),
                    "total_net_inflow": self._safe_float(row.get("北向资金净流入")),
                    "sh_balance": self._safe_float(row.get("沪股通资金余额")),
                    "sz_balance": self._safe_float(row.get("深股通资金余额")),
                    "total_balance": self._safe_float(row.get("北向资金资金余额")),
                })
            return results
        except Exception as e:
            raise DataFetchError(f"AKShare north flow fetch failed: {e}") from e

    def fetch_dragon_tiger(self, date: str = "") -> list[dict]:
        import akshare as ak

        try:
            if date:
                df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
            else:
                today = datetime.now().strftime("%Y%m%d")
                df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
            if df.empty:
                return []
            results = []
            for _, row in df.iterrows():
                results.append({
                    "symbol": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "date": str(row.get("日期", "")),
                    "buy_amount": self._safe_float(row.get("买入额")),
                    "sell_amount": self._safe_float(row.get("卖出额")),
                    "net_amount": self._safe_float(row.get("净买入额")),
                    "reason": str(row.get("上榜原因", "")),
                    "buy_broker": str(row.get("买入营业部", "")),
                    "sell_broker": str(row.get("卖出营业部", "")),
                })
            return results
        except Exception as e:
            raise DataFetchError(f"AKShare dragon tiger fetch failed: {e}") from e

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None


class YFinanceSource(DataSource):
    def fetch_daily(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        start = start_date or "2020-01-01"
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end)
            df.index.name = "date"
            df.columns = [c.lower() for c in df.columns]
            return df[["open", "high", "low", "close", "volume"]].dropna()
        except Exception as e:
            raise DataFetchError(f"YFinance fetch failed for {symbol}: {e}") from e

    def fetch_realtime(self, symbol: str) -> dict:
        import yfinance as yf

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            return {
                "symbol": symbol,
                "price": float(info.last_price or 0),
                "high": float(info.day_max or 0),
                "low": float(info.day_min or 0),
                "open": float(info.open or 0),
                "volume": float(info.last_volume or 0),
            }
        except Exception as e:
            raise DataFetchError(f"YFinance realtime fetch failed for {symbol}: {e}") from e

    def get_symbol_list(self, market: str = "US") -> pd.DataFrame:
        return pd.DataFrame(columns=["symbol", "name"])


class DataFetchError(Exception):
    pass
