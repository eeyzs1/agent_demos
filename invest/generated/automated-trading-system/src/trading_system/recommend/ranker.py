"""Rank analyzed candidates into recommendations + watchlist."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import Recommendation, ReasonItem, RiskItem


def build_recommendations(
    analyzed: List[Dict[str, Any]],
    as_of: str,
    top_n: int,
    watch_n: int,
) -> Tuple[List[Recommendation], List[Recommendation]]:
    """Sort by confidence * 0.4 + total_score * 0.6, split top/watch."""

    def sort_key(item: Dict[str, Any]) -> float:
        row = item["row"]
        total = float(
            row.get("combined_score", row.get("total", row.get("tech_score", 0))) or 0
        )
        conf = float(item.get("confidence", 50))
        penalty = 15.0 if item.get("action_hint") == "avoid" else 0.0
        return conf * 0.4 + total * 0.6 - penalty

    ordered = sorted(analyzed, key=sort_key, reverse=True)
    recs: List[Recommendation] = []
    for i, item in enumerate(ordered):
        row = item["row"]

        def _num(key, fallback=0.0):
            v = row.get(key)
            if v is None:
                return float(fallback)
            try:
                return float(v)
            except (TypeError, ValueError):
                return float(fallback)

        tech = _num("tech_score", _num("technical", 0.0) * 100.0)
        news = _num("news_score", 50.0)
        combined = _num("combined_score", _num("total", tech))
        rec = Recommendation(
            symbol=str(row.get("code") or row.get("symbol")),
            name=str(row.get("name", "")),
            as_of=as_of,
            rank=i + 1,
            scores={
                "tech_score": tech,
                "news_score": news,
                "combined_score": combined,
                "technical": _num("technical", tech / 100.0),
                "fundamental": _num("fundamental", 0.0),
                "capital_flow": _num("capital_flow", 0.0),
                "total": combined,
            },
            action_hint=str(item.get("action_hint", "watch")),
            confidence=float(item.get("confidence") or 50),
            reasons=list(item.get("reasons") or []),
            risks=list(item.get("risks") or []),
            news_summary=str(item.get("news_summary", "")),
            llm_status=str(item.get("llm_status", "fallback")),
            data_refs={"news_count": len(item.get("news_items") or [])},
            research=dict(item.get("research") or {}),
        )
        # normalize reason/risk types if dicts slipped through
        if rec.reasons and isinstance(rec.reasons[0], dict):
            rec.reasons = [ReasonItem(**r) if isinstance(r, dict) else r for r in rec.reasons]
        if rec.risks and isinstance(rec.risks[0], dict):
            rec.risks = [RiskItem(**r) if isinstance(r, dict) else r for r in rec.risks]
        recs.append(rec)

    return recs[:top_n], recs[top_n : top_n + watch_n]
