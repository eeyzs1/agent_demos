import logging
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from trading_system.data.sources import AKShareSource

logger = logging.getLogger(__name__)

CANDIDATE_LIMIT = 200
MIN_PRICE = 3.0
MAX_PE = 200
MAX_PB = 20
MIN_DAILY_VOLUME = 1_000_000
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def _retry_with_backoff(fn, fn_name: str, max_retries: int = MAX_RETRIES):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("%s 第%d次失败: %s, %0.1f秒后重试...",
                               fn_name, attempt, str(e)[:80], delay)
                time.sleep(delay)
    raise last_exc


def _to_tx_symbol(code: str) -> str:
    code = str(code).zfill(6)
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


class ScanRecommendPipeline:
    def __init__(self, source: Optional[AKShareSource] = None):
        self._source = source or AKShareSource()

    def scan_market(self, candidate_limit: int = CANDIDATE_LIMIT) -> pd.DataFrame:
        import akshare as ak

        logger.info("获取股票列表...")
        stock_list = ak.stock_info_a_code_name()
        logger.info("全市场股票数量: %d", len(stock_list))

        stock_list = stock_list[~stock_list["name"].str.contains("ST|退市|\\*ST", na=False)].copy()
        stock_list.columns = ["code", "name"]

        pe_pb_map = {}
        price_map = {}
        volume_map = {}
        amount_map = {}
        has_spot = False

        logger.info("获取Sina实时行情...")
        try:
            def _fetch_sina():
                return ak.stock_zh_a_spot()
            spot = _retry_with_backoff(_fetch_sina, "Sina行情", max_retries=2)
            cols = list(spot.columns)
            logger.debug("Sina columns: %s", cols)
            code_col = _find_col(cols, ["code", "代码"])
            price_col = _find_col(cols, ["trade", "price", "最新价"])
            pe_col_s = _find_col(cols, ["pe", "市盈率"])
            pb_col_s = _find_col(cols, ["pb", "市净率"])
            vol_col = _find_col(cols, ["volume", "成交量"])
            amt_col = _find_col(cols, ["amount", "成交额"])

            for _, row in spot.iterrows():
                c = str(row.get(code_col, ""))
                c = _normalize_code(c)
                pe_pb_map[c] = {
                    "pe": _safe_float(row.get(pe_col_s)),
                    "pb": _safe_float(row.get(pb_col_s)),
                }
                price_map[c] = _safe_float(row.get(price_col)) or 0
                volume_map[c] = _safe_float(row.get(vol_col)) or 0
                amount_map[c] = _safe_float(row.get(amt_col)) or 0
            has_spot = True
            logger.info("Sina行情获取成功: %d只", len(spot))
        except Exception as e:
            logger.warning("Sina行情获取失败: %s，将仅使用技术面评分", str(e)[:80])

        rows = []
        for _, r in stock_list.iterrows():
            code = str(r["code"]).zfill(6)
            name = str(r["name"])
            pe_pb = pe_pb_map.get(code, {})
            price = price_map.get(code, 0)
            vol = volume_map.get(code, 0)
            amt = amount_map.get(code, 0)
            pe = pe_pb.get("pe")
            pb = pe_pb.get("pb")

            if has_spot:
                if price < MIN_PRICE or vol < MIN_DAILY_VOLUME:
                    continue
                if pe is not None and (pe <= 0 or pe > MAX_PE):
                    continue
                if pb is not None and (pb <= 0 or pb > MAX_PB):
                    continue

            rows.append({
                "code": code, "name": name,
                "_price": price, "_volume": vol, "_amount": amt,
                "_pe": pe, "_pb": pb,
            })

        result = pd.DataFrame(rows)
        if has_spot and not result.empty:
            result = result.sort_values("_amount", ascending=False).head(candidate_limit)
        elif not result.empty:
            result = result.head(candidate_limit)
        logger.info("初步筛选后候选股票: %d只 (Sina行情: %s)", len(result), "可用" if has_spot else "不可用")
        return result

    def build_stock_data(self, code: str, name: str, spot_row, dragon_tiger_set: set) -> dict:
        import akshare as ak

        data = {"name": name}

        data["pe_ttm"] = spot_row.get("_pe")
        data["pb"] = spot_row.get("_pb")
        data["price"] = spot_row.get("_price", 0)

        try:
            tx_symbol = _to_tx_symbol(code)

            def _fetch():
                return ak.stock_zh_a_hist_tx(
                    symbol=tx_symbol,
                    start_date="20250501",
                    end_date=datetime.now().strftime("%Y%m%d"),
                    adjust="",
                )
            df = _retry_with_backoff(_fetch, f"{code}日线", max_retries=2)

            if not df.empty and len(df) >= 10:
                close = pd.to_numeric(df["close"], errors="coerce").dropna()
                volume = pd.to_numeric(df["amount"], errors="coerce")

                delta = close.diff()
                gain = delta.clip(lower=0)
                loss = (-delta).clip(lower=0)
                avg_gain = gain.rolling(14, min_periods=1).mean()
                avg_loss = loss.rolling(14, min_periods=1).mean()
                rs = avg_gain / avg_loss.replace(0, np.nan)
                data["rsi"] = round(float(100 - 100 / (1 + rs.iloc[-1])), 2) if pd.notna(rs.iloc[-1]) and avg_loss.iloc[-1] > 0 else 50

                ma5 = close.rolling(5, min_periods=1).mean()
                ma20 = close.rolling(20, min_periods=1).mean()
                data["ma_bullish"] = bool(ma5.iloc[-1] > ma20.iloc[-1])

                avg_vol_20 = volume.rolling(20, min_periods=1).mean()
                if pd.notna(avg_vol_20.iloc[-1]) and avg_vol_20.iloc[-1] > 0:
                    data["volume_ratio"] = round(float(volume.iloc[-1] / avg_vol_20.iloc[-1]), 2)
                else:
                    data["volume_ratio"] = 1.0

                returns = close.pct_change().dropna()
                if len(returns) >= 5:
                    data["volatility"] = round(float(returns.tail(20).std() * np.sqrt(252)), 4)
                else:
                    data["volatility"] = 0.2

                data["price_above_ma20"] = bool(close.iloc[-1] > ma20.iloc[-1])

                if data.get("price", 0) == 0:
                    data["price"] = float(close.iloc[-1])
            else:
                data.update({"rsi": 50, "ma_bullish": False, "volume_ratio": 1.0,
                            "volatility": 0.2, "price_above_ma20": False})
        except Exception:
            data.update({"rsi": 50, "ma_bullish": False, "volume_ratio": 1.0,
                        "volatility": 0.2, "price_above_ma20": False})

        try:
            fin = self._source.fetch_financial(code)
            data["roe"] = fin.get("roe")
            data["revenue_growth"] = fin.get("revenue_growth")
        except Exception:
            data["roe"] = None
            data["revenue_growth"] = None

        data["north_net_inflow"] = 0
        data["main_net_inflow"] = 0
        data["on_dragon_tiger"] = code in dragon_tiger_set
        data["news_sentiment"] = 0
        data["sector_heat"] = 50
        data["market_mood"] = 50

        return data

    def _fetch_dragon_tiger_set(self) -> set:
        try:
            today = datetime.now().strftime("%Y%m%d")
            records = self._source.fetch_dragon_tiger(date=today)
            return {str(r.get("symbol", "")).zfill(6) for r in records}
        except Exception:
            return set()

    def run(self, candidate_limit: int = CANDIDATE_LIMIT) -> tuple[list, dict]:
        try:
            spot_df = self.scan_market(candidate_limit=candidate_limit)
        except Exception as e:
            logger.error("全市场扫描失败: %s", e)
            raise RuntimeError(
                f"无法获取全市场行情数据（{str(e)[:100]}）。请检查网络或稍后重试。"
            ) from e

        if spot_df.empty:
            raise RuntimeError("筛选后没有符合条件的股票，请降低筛选门槛或检查数据源")

        dragon_tiger_set = self._fetch_dragon_tiger_set()
        logger.info("龙虎榜上榜股票: %d只", len(dragon_tiger_set))

        stock_data_list = []
        total = len(spot_df)
        errors = 0

        for i, (_, row) in enumerate(spot_df.iterrows()):
            code = str(row["code"])
            name = str(row.get("name", ""))
            logger.info("[%d/%d] 分析 %s %s", i + 1, total, code, name)

            try:
                data = self.build_stock_data(code, name, row, dragon_tiger_set)
                if data.get("price", 0) > 0:
                    stock_data_list.append((code, data))
                time.sleep(0.15)
            except Exception as e:
                errors += 1
                logger.warning("跳过 %s %s: %s", code, name, str(e)[:100])
                continue

        logger.info("数据获取完成: %d只有效, %d只跳过", len(stock_data_list), errors)

        market_summary = self._build_market_summary()
        return stock_data_list, market_summary

    def _build_market_summary(self) -> dict:
        north_info = "数据获取失败"
        try:
            north_data = self._source.fetch_north_flow()
            if north_data:
                latest = north_data[-1]
                net = latest.get("total_net_inflow")
                if net is not None:
                    north_info = f"净买额 {net:.2f}亿"
        except Exception:
            pass

        return {
            "北向资金": north_info,
            "市场情绪": "正常",
            "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def _safe_float(val):
    if val is None:
        return None
    try:
        v = float(val)
        if pd.isna(v):
            return None
        return v
    except (ValueError, TypeError):
        return None


def _find_col(columns: list, candidates: list) -> str:
    for c in candidates:
        if c in columns:
            return c
    return candidates[0]


def _normalize_code(code: str) -> str:
    code = str(code).strip()
    for prefix in ("sh", "sz", "SH", "SZ"):
        if code.startswith(prefix):
            return code[len(prefix):].zfill(6)
    return code.zfill(6)