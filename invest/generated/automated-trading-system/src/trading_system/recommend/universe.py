"""Build A-share main-board universe."""

from __future__ import annotations

import logging
from typing import List, Optional, Set

import pandas as pd

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..data.fetcher import MarketDataFetcher
from .models import SymbolMeta

logger = logging.getLogger(__name__)


def is_mainboard_code(code: str) -> bool:
    """沪主板 600/601/603；深主板 000/001/002（含原中小板）。排除创业/科创/北交所。"""
    c = str(code).strip().zfill(6)
    if not c.isdigit() or len(c) != 6:
        return False
    if c.startswith(("688", "689", "300", "301", "8", "4")):
        return False
    return c.startswith(("600", "601", "603", "000", "001", "002"))


class UniverseBuilder:
    def __init__(self, config_dir: str = "config"):
        self._cfg = get_config(config_dir)
        self._fetcher = MarketDataFetcher(config_dir)
        self._audit = get_audit_logger()
        self.config_dir = config_dir

    def build(self, universe: Optional[str] = None) -> List[SymbolMeta]:
        universe = universe or self._cfg.get("recommend.universe", "mainboard")
        exclude_st = bool(self._cfg.get("recommend.exclude_st", True))
        max_score = int(self._cfg.get("recommend.max_score_stocks", 400) or 0)

        if universe == "custom":
            codes: List[str] = list(self._cfg.get("recommend.custom_symbols", []) or [])
            stock_list = self._fetcher.get_stock_list()
            name_map = {}
            if stock_list is not None and not stock_list.empty and "code" in stock_list.columns:
                for _, row in stock_list.iterrows():
                    name_map[str(row["code"]).zfill(6)] = str(row.get("name", ""))
            symbols = [
                SymbolMeta(code=str(c).zfill(6), name=name_map.get(str(c).zfill(6), str(c)))
                for c in codes
            ]
        else:
            df = self._fetcher.get_stock_list()
            symbols = self._from_frame(df, exclude_st=exclude_st)

        filtered_out = 0
        if max_score > 0 and len(symbols) > max_score:
            filtered_out = len(symbols) - max_score
            # Prefer higher liquidity proxies later; for now keep stable order by code then cap
            symbols = sorted(symbols, key=lambda s: s.code)[:max_score]

        self._audit.log(
            "universe_built",
            check_id="recommend.universe",
            result="OK",
            payload={
                "universe": universe,
                "count": len(symbols),
                "capped_out": filtered_out,
                "max_score_stocks": max_score,
            },
        )
        logger.info("Universe %s → %d symbols (capped_out=%d)", universe, len(symbols), filtered_out)
        return symbols

    def _from_frame(self, df: pd.DataFrame, exclude_st: bool) -> List[SymbolMeta]:
        if df is None or df.empty:
            return []
        out: List[SymbolMeta] = []
        seen: Set[str] = set()
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip().zfill(6)
            name = str(row.get("name", "")).strip()
            if not code or code in seen:
                continue
            if not is_mainboard_code(code):
                continue
            if exclude_st and ("ST" in name.upper() or "*ST" in name):
                continue
            if "退" in name:
                continue
            seen.add(code)
            out.append(
                SymbolMeta(
                    code=code,
                    name=name,
                    market=str(row.get("market", "")),
                    list_date=str(row.get("list_date", "")),
                )
            )
        return out
