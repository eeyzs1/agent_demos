"""News sentiment scorer — numeric news_score (0-100) + raw articles for agent judge.

tech_score comes from price/volume factors; news_score comes from headlines/body
keyword polarity + coverage. Raw news text is always preserved for Cursor/LLM final judgment.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import get_config
from ..data.fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = [
    "增长", "盈利", "突破", "利好", "回购", "增持", "分红", "业绩预增", "中标",
    "签约", "创新", "升级", "获批", "订单", "超预期", "扭亏", "扩产", "新品",
    "合作", "上升", "新高", "龙头", "领先", "优势", "涨停", "加码", "注入",
    "重组成功", "高增", "回暖", "复苏", "政策支持", "国产替代",
]

NEGATIVE_KEYWORDS = [
    "亏损", "下滑", "下跌", "利空", "减持", "处罚", "违规", "立案", "退市",
    "暴雷", "造假", "亏损扩大", "业绩预减", "下调", "风险提示", "停产",
    "召回", "诉讼", "违约", "爆仓", "质押平仓", "商誉减值", "问询函",
    "警示", "跌停", "裁员", "破产", "冻结", "查处",
]


@dataclass
class NewsScoreResult:
    symbol: str
    news_score: float  # 0-100
    label: str  # positive | neutral | negative | no_data
    article_count: int
    positive_hits: int
    negative_hits: int
    confidence: float  # 0-1, based on coverage / keyword hits
    key_keywords: List[str] = field(default_factory=list)
    articles: List[Dict[str, Any]] = field(default_factory=list)
    analyzed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NewsScorer:
    """Fetch news and convert to a reproducible 0-100 news_score."""

    def __init__(self, config_dir: str = "config"):
        self._cfg = get_config(config_dir)
        self._fetcher = MarketDataFetcher(config_dir)
        self._pos = list(self._cfg.get("recommend.news.positive_keywords", POSITIVE_KEYWORDS) or POSITIVE_KEYWORDS)
        self._neg = list(self._cfg.get("recommend.news.negative_keywords", NEGATIVE_KEYWORDS) or NEGATIVE_KEYWORDS)
        self._cache: Dict[str, NewsScoreResult] = {}

    def score_symbol(self, symbol: str, limit: Optional[int] = None) -> NewsScoreResult:
        symbol = str(symbol).zfill(6)
        if symbol in self._cache:
            return self._cache[symbol]
        limit = int(limit or self._cfg.get("recommend.news_per_symbol", 8))
        articles = self._fetcher.get_stock_news(symbol, limit=limit)
        result = self.score_articles(symbol, articles)
        self._cache[symbol] = result
        return result

    def score_articles(self, symbol: str, articles: List[Dict[str, Any]]) -> NewsScoreResult:
        if not articles:
            return NewsScoreResult(
                symbol=symbol,
                news_score=50.0,
                label="no_data",
                article_count=0,
                positive_hits=0,
                negative_hits=0,
                confidence=0.0,
                articles=[],
                analyzed_at=datetime.now().isoformat(timespec="seconds"),
            )

        per_article: List[float] = []
        pos_total = 0
        neg_total = 0
        kw_hits: Dict[str, int] = {}

        cleaned: List[Dict[str, Any]] = []
        for a in articles:
            if not isinstance(a, dict):
                continue
            title = str(a.get("title") or "").strip()
            content = str(a.get("content") or "").strip()
            text = f"{title} {content}".strip()
            if not text:
                continue
            cleaned.append(
                {
                    "title": title,
                    "content": content[:500],
                    "datetime": str(a.get("datetime") or ""),
                    "source": str(a.get("source") or ""),
                }
            )
            p, n, hits = self._polarity(text)
            pos_total += p
            neg_total += n
            for k, c in hits.items():
                kw_hits[k] = kw_hits.get(k, 0) + c
            if p + n == 0:
                per_article.append(0.0)  # neutral article in [-1,1]
            else:
                per_article.append((p - n) / (p + n))

        if not cleaned:
            return self.score_articles(symbol, [])

        # mean polarity in [-1, 1] → [0, 100]
        mean_pol = sum(per_article) / len(per_article)
        news_score = round(max(0.0, min(100.0, (mean_pol + 1.0) * 50.0)), 2)

        # slight coverage boost/penalty: more articles → slightly more extreme trust later via confidence
        if mean_pol >= 0.25:
            label = "positive"
        elif mean_pol <= -0.25:
            label = "negative"
        else:
            label = "neutral"

        hit_mass = pos_total + neg_total
        confidence = round(
            min(1.0, 0.25 * len(cleaned) / 4.0 + 0.75 * min(1.0, hit_mass / 8.0)),
            4,
        )
        top_kw = sorted(kw_hits.items(), key=lambda x: x[1], reverse=True)[:8]

        return NewsScoreResult(
            symbol=symbol,
            news_score=news_score,
            label=label,
            article_count=len(cleaned),
            positive_hits=pos_total,
            negative_hits=neg_total,
            confidence=confidence,
            key_keywords=[k for k, _ in top_kw],
            articles=cleaned,
            analyzed_at=datetime.now().isoformat(timespec="seconds"),
        )

    def _polarity(self, text: str) -> Tuple[int, int, Dict[str, int]]:
        hits: Dict[str, int] = {}
        pos = 0
        neg = 0
        for kw in self._pos:
            c = text.count(kw)
            if c:
                pos += c
                hits[kw] = hits.get(kw, 0) + c
        for kw in self._neg:
            c = text.count(kw)
            if c:
                neg += c
                hits[kw] = hits.get(kw, 0) + c
        return pos, neg, hits
