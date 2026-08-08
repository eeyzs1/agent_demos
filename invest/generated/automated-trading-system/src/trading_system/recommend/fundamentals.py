"""Extract PE/PB/ROE and growth snapshots for agent research briefs."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import pandas as pd

from ..data.fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)


def _pick_col(columns, *candidates: str) -> Optional[str]:
    cols = list(columns)
    lower = {str(c).strip().lower(): c for c in cols}
    for name in candidates:
        key = name.strip().lower()
        if key in lower:
            return lower[key]
    for name in candidates:
        key = name.strip().lower()
        for c in cols:
            if key in str(c).strip().lower():
                return c
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"False", "None", "-", "--"}:
        return None
    # e.g. 10.57% / 1.47%
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*%$", text)
    if m:
        return float(m.group(1))
    # strip Chinese unit suffixes like 亿
    text = re.sub(r"[亿万千百]", "", text)
    try:
        return float(text)
    except ValueError:
        return None


def extract_fundamentals(
    symbol: str,
    fetcher: MarketDataFetcher,
) -> Dict[str, Any]:
    """Build a fundamentals snapshot for one symbol.

    Uses East Money valuation series (PE/PB) + THS financial abstract (ROE/growth).
    Missing fields are null; ``data_sparse`` is True when PE/PB/ROE all missing.
    """
    code = str(symbol).zfill(6)
    out: Dict[str, Any] = {
        "pe_ttm": None,
        "pe_static": None,
        "pb": None,
        "ps": None,
        "peg": None,
        "roe": None,
        "revenue_yoy": None,
        "net_profit_yoy": None,
        "report_date": None,
        "valuation_as_of": None,
        "close": None,
        "data_sparse": True,
        "source": {
            "valuation": "akshare.stock_value_em",
            "financials": "akshare.stock_financial_abstract_ths",
        },
    }

    try:
        val = fetcher.get_valuation_data(code)
        if val is not None and not val.empty:
            row = val.iloc[-1]
            pe_col = _pick_col(val.columns, "PE(TTM)", "pe(ttm)", "市盈率(TTM)")
            pe_s = _pick_col(val.columns, "PE(静)", "PE(静)", "市盈率")
            pb_col = _pick_col(val.columns, "市净率", "pb")
            ps_col = _pick_col(val.columns, "市销率", "ps")
            peg_col = _pick_col(val.columns, "PEG值", "PEG", "peg")
            date_col = _pick_col(val.columns, "数据日期", "date")
            close_col = _pick_col(val.columns, "当日收盘价", "收盘价", "close")
            out["pe_ttm"] = _to_float(row[pe_col]) if pe_col else None
            out["pe_static"] = _to_float(row[pe_s]) if pe_s else None
            out["pb"] = _to_float(row[pb_col]) if pb_col else None
            out["ps"] = _to_float(row[ps_col]) if ps_col else None
            out["peg"] = _to_float(row[peg_col]) if peg_col else None
            out["close"] = _to_float(row[close_col]) if close_col else None
            if date_col is not None:
                out["valuation_as_of"] = str(row[date_col])
    except Exception as e:
        logger.warning("valuation extract failed for %s: %s", code, e)

    try:
        fin = fetcher.get_financial_data(code)
        if fin is not None and not fin.empty:
            row = fin.iloc[-1]
            roe_col = _pick_col(fin.columns, "净资产收益率", "roe")
            rev_col = _pick_col(fin.columns, "营业总收入同比增长率", "revenue_yoy")
            np_col = _pick_col(fin.columns, "净利润同比增长", "净利润同比增长率", "net_profit_yoy")
            rpt_col = _pick_col(fin.columns, "报告期", "report_date", "date")
            out["roe"] = _to_float(row[roe_col]) if roe_col else None
            out["revenue_yoy"] = _to_float(row[rev_col]) if rev_col else None
            out["net_profit_yoy"] = _to_float(row[np_col]) if np_col else None
            if rpt_col is not None:
                out["report_date"] = str(row[rpt_col])
    except Exception as e:
        logger.warning("financial extract failed for %s: %s", code, e)

    out["data_sparse"] = all(
        out[k] is None for k in ("pe_ttm", "pb", "roe")
    )
    return out
