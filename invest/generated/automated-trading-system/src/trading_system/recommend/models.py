"""Data models for daily recommendation pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SymbolMeta:
    code: str
    name: str
    market: str = ""
    list_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReasonItem:
    code: str
    text: str
    weight: float = 0.0
    source: str = "llm"  # llm | rule | news

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskItem:
    code: str
    text: str
    source: str = "llm"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Recommendation:
    symbol: str
    name: str
    as_of: str
    rank: int
    scores: Dict[str, float]
    action_hint: str  # strong_watch | watch | avoid
    confidence: float  # 0-100
    reasons: List[ReasonItem] = field(default_factory=list)
    risks: List[RiskItem] = field(default_factory=list)
    news_summary: str = ""
    llm_status: str = "ok"  # ok | fallback | error
    data_refs: Dict[str, Any] = field(default_factory=dict)
    research: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "as_of": self.as_of,
            "rank": self.rank,
            "scores": self.scores,
            "action_hint": self.action_hint,
            "confidence": self.confidence,
            "reasons": [r.to_dict() for r in self.reasons],
            "risks": [r.to_dict() for r in self.risks],
            "news_summary": self.news_summary,
            "llm_status": self.llm_status,
            "data_refs": self.data_refs,
            "research": self.research,
        }


@dataclass
class DailyReport:
    as_of: str
    universe: str
    market_overview: str
    recommendations: List[Recommendation]
    watchlist: List[Recommendation]
    llm_enabled: bool
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "universe": self.universe,
            "market_overview": self.market_overview,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "watchlist": [r.to_dict() for r in self.watchlist],
            "llm_enabled": self.llm_enabled,
            "meta": self.meta,
        }
