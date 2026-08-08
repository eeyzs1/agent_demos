"""Dual-track scoring: tech_score (price factors) + news_score (news polarity)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..data.fetcher import MarketDataFetcher
from ..pipeline.screener import StockScreener
from .models import SymbolMeta
from .news_score import NewsScorer

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self._cfg = get_config(config_dir)
        self._screener = StockScreener(config_dir)
        self._fetcher = MarketDataFetcher(config_dir)
        self._news = NewsScorer(config_dir)
        self._audit = get_audit_logger()
        self.w_tech = float(self._cfg.get("recommend.dual_scores.tech_weight", 0.60))
        self.w_news = float(self._cfg.get("recommend.dual_scores.news_weight", 0.40))

    def score_universe(
        self,
        symbols: List[SymbolMeta],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Score universe on technical track only (fast path for ranking)."""
        lookback = int(self._cfg.get("recommend.lookback_days", 120))
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=lookback + 40)).strftime("%Y%m%d")

        rows = []
        failures = 0
        total = len(symbols)
        for i, sym in enumerate(symbols):
            try:
                daily = self._fetcher.get_daily_data(sym.code, start_date, end_date)
                scores = self._screener.score_stock(sym.code, daily)
                tech_score = round(float(scores["technical"]) * 100.0, 2)
                rows.append(
                    {
                        "code": sym.code,
                        "name": sym.name,
                        "tech_score": tech_score,
                        "technical": scores["technical"],
                        "fundamental": scores["fundamental"],
                        "capital_flow": scores["capital_flow"],
                        # legacy placeholder — not news; kept for compat, prefer news_score
                        "sentiment": scores["sentiment"],
                        "news_score": None,
                        "news_label": None,
                        "news_confidence": None,
                        "combined_score": tech_score,
                        "total": tech_score,  # pre-news ranking uses tech
                    }
                )
            except Exception as e:
                failures += 1
                logger.debug("score failed %s: %s", sym.code, e)
            if (i + 1) % 50 == 0:
                logger.info("Tech-scored %d/%d (failures=%d)", i + 1, total, failures)

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("tech_score", ascending=False).reset_index(drop=True)
        self._audit.log(
            "scoring_complete",
            check_id="recommend.scoring",
            result="OK",
            payload={"scored": len(df), "universe": total, "failures": failures, "track": "tech"},
        )
        return df

    def enrich_with_news(self, scored: pd.DataFrame, n: Optional[int] = None) -> pd.DataFrame:
        """Attach news_score + articles meta for top-N tech candidates; recompute combined."""
        if scored is None or scored.empty:
            return pd.DataFrame()
        n = int(n or self._cfg.get("recommend.llm_candidate_n", 30))
        df = scored.head(n).copy().reset_index(drop=True)
        news_scores = []
        news_labels = []
        news_conf = []
        news_counts = []
        combined = []

        for _, row in df.iterrows():
            code = str(row["code"])
            result = self._news.score_symbol(code)
            ns = float(result.news_score)
            ts = float(row["tech_score"])
            # If no news data, down-weight news toward neutral and lower combined trust later
            if result.label == "no_data":
                comb = round(ts * (self.w_tech + self.w_news * 0.5) + 50.0 * (self.w_news * 0.5), 2)
            else:
                comb = round(ts * self.w_tech + ns * self.w_news, 2)
            news_scores.append(ns)
            news_labels.append(result.label)
            news_conf.append(result.confidence)
            news_counts.append(result.article_count)
            combined.append(comb)

        df["news_score"] = news_scores
        df["news_label"] = news_labels
        df["news_confidence"] = news_conf
        df["news_article_count"] = news_counts
        df["combined_score"] = combined
        df["total"] = combined
        df = df.sort_values("combined_score", ascending=False).reset_index(drop=True)
        self._audit.log(
            "news_enrich_complete",
            check_id="recommend.news",
            result="OK",
            payload={"enriched": len(df), "w_tech": self.w_tech, "w_news": self.w_news},
        )
        return df

    def top_frame(self, scored: pd.DataFrame, n: int) -> pd.DataFrame:
        if scored is None or scored.empty:
            return pd.DataFrame()
        min_score = float(self._cfg.get("recommend.min_total_score", 0) or 0)
        col = "combined_score" if "combined_score" in scored.columns else "tech_score"
        df = scored
        if min_score > 0 and col in df.columns:
            # min_total_score historically ~55 on 0-100-ish scales
            df = df[df[col] >= min_score]
        return df.head(n).reset_index(drop=True)
