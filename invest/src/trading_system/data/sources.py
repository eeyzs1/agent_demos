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
            spot_df = ak.stock_zh_a_spot_em()
            row = spot_df[spot_df["代码"] == symbol]
            if not row.empty:
                r = row.iloc[0]
                pe_col = None
                pb_col = None
                for col in spot_df.columns:
                    if "市盈率" in col:
                        pe_col = col
                    if "市净率" in col:
                        pb_col = col
                if pe_col:
                    result["pe_ttm"] = self._safe_float(r.get(pe_col))
                if pb_col:
                    result["pb"] = self._safe_float(r.get(pb_col))
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
                result["eps"] = self._safe_float(latest.get("每股收益(元)"))
                result["bps"] = self._safe_float(latest.get("每股净资产(元)"))
                if not result["report_date"]:
                    result["report_date"] = str(latest.get("日期", ""))
        except Exception:
            pass

        try:
            df_growth = ak.stock_profit_sheet_by_yearly_em(symbol=symbol)
            if not df_growth.empty and len(df_growth) >= 2:
                latest = df_growth.iloc[0]
                prev = df_growth.iloc[1]
                rev_latest = self._safe_float(latest.get("营业总收入"))
                rev_prev = self._safe_float(prev.get("营业总收入"))
                if rev_latest and rev_prev and rev_prev > 0:
                    result["revenue_growth"] = round(
                        (rev_latest - rev_prev) / rev_prev * 100, 2
                    )
                profit_latest = self._safe_float(latest.get("净利润"))
                profit_prev = self._safe_float(prev.get("净利润"))
                if profit_latest and profit_prev and abs(profit_prev) > 0:
                    result["net_profit_growth"] = round(
                        (profit_latest - profit_prev) / abs(profit_prev) * 100, 2
                    )
                if not result["report_date"]:
                    result["report_date"] = str(latest.get("报告期", ""))
        except Exception:
            pass

        return result

    def fetch_north_flow(self) -> list[dict]:
        import akshare as ak

        try:
            df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if df.empty:
                return []
            results = []
            for _, row in df.iterrows():
                results.append({
                    "date": str(row.get("日期", "")),
                    "total_net_inflow": self._safe_float(row.get("当日成交净买额")),
                    "buy_amount": self._safe_float(row.get("买入成交额")),
                    "sell_amount": self._safe_float(row.get("卖出成交额")),
                    "cumulative_net": self._safe_float(row.get("历史累计净买额")),
                    "daily_inflow": self._safe_float(row.get("当日资金流入")),
                    "daily_balance": self._safe_float(row.get("当日余额")),
                    "holding_value": self._safe_float(row.get("持股市值")),
                    "leading_stock": str(row.get("领涨股", "")),
                    "leading_stock_code": str(row.get("领涨股-代码", "")),
                    "hs300": self._safe_float(row.get("沪深300")),
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
