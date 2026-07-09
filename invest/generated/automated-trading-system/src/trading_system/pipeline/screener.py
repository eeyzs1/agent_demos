"""Stock screener — multi-factor scoring: technical(40%) + fundamental(30%) +
capital flow(20%) + sentiment(10%). Depends only on core & data (AR004)."""

import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.event_bus import get_event_bus
from ..data.fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)

_COL_MAP = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
    "最低": "low", "成交量": "volume", "成交额": "amount",
    "振幅": "amplitude", "涨跌幅": "change_pct", "涨跌额": "change_amount",
    "换手率": "turnover_rate",
}
_KEYS = ["technical", "fundamental", "capital_flow", "sentiment", "total"]


class StockScreener:
    """Multi-factor stock screener for A-share. All params from YAML config.
    Inter-module communication via EventBus (AR001). No risk/execution imports (AR004)."""

    def __init__(self, config_dir: str = "config"):
        cfg = get_config(config_dir)
        self._event_bus = get_event_bus()
        self._audit = get_audit_logger()
        self._fetcher = MarketDataFetcher(config_dir)
        self.w_tech = cfg.get("screening.factor_weights.technical", 0.40)
        self.w_fund = cfg.get("screening.factor_weights.fundamental", 0.30)
        self.w_cap = cfg.get("screening.factor_weights.capital", 0.20)
        self.w_sent = cfg.get("screening.factor_weights.sentiment", 0.10)
        self.exclude_st = cfg.get("screening.exclude_st", True)
        self.min_listing_days = cfg.get("screening.exclude_new_listings_days", 60)
        self.rsi_period = cfg.get("strategy.default_params.mean_reversion.rsi_period", 14)
        self.ma_short = cfg.get("strategy.default_params.trend_following.ma_short", 20)
        self.ma_long = cfg.get("strategy.default_params.trend_following.ma_long", 60)
        self.bb_period = cfg.get("strategy.default_params.mean_reversion.bollinger_period", 20)
        self.bb_std = cfg.get("strategy.default_params.mean_reversion.bollinger_std", 2.0)
        self.macd_fast = cfg.get("screening.macd_fast", 12)
        self.macd_slow = cfg.get("screening.macd_slow", 26)
        self.macd_signal = cfg.get("screening.macd_signal", 9)
        self.vol_short = cfg.get("screening.vol_short_period", 5)
        self.vol_long = cfg.get("screening.vol_long_period", 20)
        self._sector_momentum: dict = {}

    def _rsi(self, close: pd.Series, period: int) -> float:
        if len(close) < period + 1:
            return np.nan
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        val = (100.0 - 100.0 / (1.0 + rs)).iloc[-1]
        return float(val) if not np.isnan(val) else np.nan

    def _macd(self, close: pd.Series):
        ef = close.ewm(span=self.macd_fast, adjust=False).mean()
        es = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd = ef - es
        signal = macd.ewm(span=self.macd_signal, adjust=False).mean()
        hist = macd - signal
        return float(macd.iloc[-1]), float(signal.iloc[-1]), float(hist.iloc[-1])

    def _score_technical(self, df: pd.DataFrame) -> float:
        close = df["close"]
        vol = df.get("volume", pd.Series(dtype=float))
        rsi_v = self._rsi(close, self.rsi_period)
        rsi_s = 1.0 - abs((rsi_v - 50.0) / 50.0) if not np.isnan(rsi_v) else 0.5
        _, _, hist = self._macd(close)
        macd_s = 0.5 + 0.5 * np.tanh(hist / close.iloc[-1] * 100) if not np.isnan(hist) else 0.5
        ma_s = close.rolling(self.ma_short).mean().iloc[-1]
        ma_l = close.rolling(self.ma_long).mean().iloc[-1]
        ma_s = 0.7 if ma_s > ma_l else 0.3
        v_avg = vol.rolling(self.vol_short).mean().iloc[-1] if len(vol) >= self.vol_short else 1.0
        vol_s = min(1.0, (vol.iloc[-1] / v_avg) / 2.0) if v_avg and v_avg > 0 else 0.5
        mid = close.rolling(self.bb_period).mean().iloc[-1]
        std = close.rolling(self.bb_period).std().iloc[-1]
        up, lo = mid + self.bb_std * std, mid - self.bb_std * std
        bb_s = 1.0 - abs((close.iloc[-1] - lo) / (up - lo) - 0.5) * 2.0 if up > lo else 0.5
        return round(rsi_s * 0.25 + macd_s * 0.25 + ma_s * 0.20 + vol_s * 0.15 + bb_s * 0.15, 4)

    def _score_fundamental(self, stock_code: str) -> float:
        try:
            fin = self._fetcher.get_financial_data(stock_code)
        except Exception:
            return 0.5
        if fin is None or fin.empty:
            return 0.5
        cols = {str(c).strip().lower(): c for c in fin.columns}
        scores = []
        pe = cols.get("市盈率") or cols.get("pe")
        if pe:
            s = pd.to_numeric(fin[pe], errors="coerce").dropna()
            if not s.empty:
                scores.append(1.0 - min(max(float(s.iloc[-1]), 0), 200) / 200.0)
        pb = cols.get("市净率") or cols.get("pb")
        if pb:
            s = pd.to_numeric(fin[pb], errors="coerce").dropna()
            if not s.empty:
                scores.append(1.0 - min(max(float(s.iloc[-1]), 0), 20) / 20.0)
        roe = cols.get("净资产收益率") or cols.get("roe")
        if roe:
            s = pd.to_numeric(fin[roe], errors="coerce").dropna()
            if not s.empty:
                scores.append(min(max(float(s.iloc[-1]) / 30.0, 0.0), 1.0))
        for col_name in [(cols.get("营业总收入") or cols.get("revenue")),
                         (cols.get("净利润") or cols.get("net_profit"))]:
            if col_name:
                s = pd.to_numeric(fin[col_name], errors="coerce").dropna()
                if len(s) >= 2:
                    g = float(s.iloc[-1] / s.iloc[-2] - 1.0)
                    scores.append(min(max(g, -0.3), 0.5) / 0.5 * 0.5 + 0.5)
        return round(sum(scores) / len(scores), 4) if scores else 0.5

    def _score_capital_flow(self, df: pd.DataFrame) -> float:
        chg = df.get("change_pct", pd.Series(dtype=float))
        turnover = df.get("turnover_rate", pd.Series(dtype=float))
        vol = df.get("volume", pd.Series(dtype=float))
        chg_v = float(chg.iloc[-1]) if not chg.empty and not np.isnan(chg.iloc[-1]) else 0.0
        chg_s = min(max((chg_v + 5.0) / 10.0, 0.0), 1.0)
        to_v = float(turnover.iloc[-1]) if not turnover.empty and not np.isnan(turnover.iloc[-1]) else 0.0
        to_s = max(1.0 - abs(to_v - 5.0) / 10.0, 0.0) if to_v < 15 else 0.0
        if len(vol) >= self.vol_long:
            v20 = vol.rolling(self.vol_long).mean().iloc[-1]
            vr_s = min(vol.iloc[-1] / v20 / 2.0, 1.0) if v20 > 0 else 0.5
        else:
            vr_s = 0.5
        return round(chg_s * 0.35 + to_s * 0.35 + vr_s * 0.30, 4)

    def _score_sentiment(self, df: pd.DataFrame, stock_code: str) -> float:
        scores = []
        try:
            scores.append(0.7 if self._fetcher.get_market_sentiment_data().get(
                "breadth_available", False) else 0.5)
        except Exception:
            scores.append(0.5)
        try:
            stocks = self._fetcher.get_stock_list()
            m = stocks[stocks["code"].astype(str).str.strip() == str(stock_code).strip()]
            sector = str(m.iloc[0].get("industry", "")) if not m.empty else ""
        except Exception:
            sector = ""
        sm = self._sector_momentum.get(sector) if sector else None
        scores.append(min(max(sm, 0.0), 1.0) if sm is not None else 0.5)
        return round(sum(scores) / len(scores), 4)

    def score_stock(self, stock_code: str, daily_data: pd.DataFrame = None) -> dict:
        """Score a stock across all factors. Returns dict with factor scores & total."""
        if daily_data is None:
            daily_data = self._fetcher.get_daily_data(str(stock_code))
        if daily_data is None or daily_data.empty:
            return dict.fromkeys(_KEYS, 0.0)
        df = daily_data.copy()
        df.columns = [c.lower() if isinstance(c, str) else c for c in df.columns]
        df = df.rename(columns=_COL_MAP)
        if "close" not in df.columns:
            return dict.fromkeys(_KEYS, 0.0)
        tech = self._score_technical(df)
        fund = self._score_fundamental(stock_code)
        cap = self._score_capital_flow(df)
        sent = self._score_sentiment(df, stock_code)
        total = round(tech * self.w_tech + fund * self.w_fund + cap * self.w_cap + sent * self.w_sent, 4)
        return {"technical": tech, "fundamental": fund, "capital_flow": cap,
                "sentiment": sent, "total": total}

    def screen(self, stock_list: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        """Screen a universe of stocks, return scored DataFrame sorted by total."""
        cutoff = (datetime.now() - timedelta(days=self.min_listing_days)).strftime("%Y%m%d")
        results, total = [], len(stock_list)
        for idx, (_, row) in enumerate(stock_list.iterrows()):
            code = str(row.get("code", "")).strip()
            name = str(row.get("name", "")).strip()
            if not code or not name:
                continue
            if self.exclude_st and ("ST" in name.upper() or "*ST" in name.upper()):
                continue
            if "退" in name:
                continue
            ld = str(row.get("list_date", "")).strip()
            if ld and ld.replace("-", "").isdigit() and ld.replace("-", "") > cutoff:
                continue
            try:
                daily = self._fetcher.get_daily_data(code, start_date, end_date)
                s = self.score_stock(code, daily)
                results.append({"code": code, "name": name,
                                "technical": s["technical"], "fundamental": s["fundamental"],
                                "capital_flow": s["capital_flow"], "sentiment": s["sentiment"],
                                "total": s["total"]})
            except Exception:
                logger.debug("Skipping %s — data fetch failed", code)
            if (idx + 1) % 200 == 0:
                logger.info("Screened %d/%d stocks", idx + 1, total)
        df = pd.DataFrame(results)
        if not df.empty:
            df = df.sort_values("total", ascending=False).reset_index(drop=True)
        self._audit.log("screening_complete", check_id="screen", result="OK",
                        payload={"candidates": len(df), "universe": total})
        self._event_bus.publish("pipeline.screening_complete",
                                {"candidates": len(df), "universe": total})
        return df

    def get_top_candidates(self, df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
        """Return top-N candidates sorted by total score."""
        if df is None or df.empty or "total" not in df.columns:
            return pd.DataFrame()
        top = df.sort_values("total", ascending=False).head(n).reset_index(drop=True)
        self._event_bus.publish("pipeline.top_candidates", {"count": len(top), "top_n": n})
        return top