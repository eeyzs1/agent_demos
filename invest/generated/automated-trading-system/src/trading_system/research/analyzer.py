"""ResearchAnalyzer — Fundamental analysis engine.

Performs fundamental research analysis including:
- News sentiment analysis (keyword-based NLP scoring)
- Research report summary generation
- Announcement scanning (positive/negative events)

Output: key findings + risk warnings with confidence scores.
Depends only on data and core, NOT on risk or execution.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.event_bus import get_event_bus

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data Classes
# ------------------------------------------------------------------


@dataclass
class NewsSentimentResult:
    """Result of news sentiment analysis for a single symbol."""

    symbol: str
    overall_score: float  # -1.0 (very negative) to 1.0 (very positive)
    sentiment_label: str  # "positive", "neutral", "negative"
    article_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    key_keywords: List[str] = field(default_factory=list)
    confidence: float = 1.0
    analyzed_at: str = ""


@dataclass
class AnnouncementResult:
    """Result of announcement scanning for a single symbol."""

    symbol: str
    total_announcements: int
    positive_events: List[Dict[str, Any]] = field(default_factory=list)
    negative_events: List[Dict[str, Any]] = field(default_factory=list)
    risk_warnings: List[Dict[str, Any]] = field(default_factory=list)
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    overall_impact: str = "neutral"  # "positive", "neutral", "negative"
    confidence: float = 1.0
    analyzed_at: str = ""


@dataclass
class ResearchSummary:
    """Aggregated research summary for a symbol."""

    symbol: str
    news_sentiment: Optional[NewsSentimentResult] = None
    announcement_result: Optional[AnnouncementResult] = None
    key_findings: List[Dict[str, Any]] = field(default_factory=list)
    risk_warnings: List[Dict[str, Any]] = field(default_factory=list)
    overall_score: float = 0.0  # -1.0 to 1.0
    overall_label: str = "neutral"
    confidence: float = 1.0
    generated_at: str = ""


# ------------------------------------------------------------------
# ResearchAnalyzer
# ------------------------------------------------------------------


class ResearchAnalyzer:
    """Fundamental research analysis engine.

    Provides news sentiment analysis, announcement scanning, and
    research report summary generation. Publishes
    "research.analysis_complete" events.
    """

    DEFAULT_POSITIVE_KEYWORDS: List[str] = [
        "增长", "盈利", "突破", "利好", "回购", "增持", "分红",
        "业绩预增", "中标", "签约", "创新", "升级", "获批",
        "订单", "超预期", "扭亏", "扩产", "新品", "合作",
        "上升", "新高", "龙头", "领先", "优势",
        "growing", "profit", "breakthrough", "upgrade", "buyback",
        "dividend", "contract", "innovation", "approval",
    ]

    DEFAULT_NEGATIVE_KEYWORDS: List[str] = [
        "下跌", "亏损", "减持", "诉讼", "处罚", "退市",
        "债务违约", "商誉减值", "业绩预亏", "停工", "停产",
        "解禁", "质押", "爆雷", "立案", "调查", "警告",
        "风险", "下滑", "预警", "危机", "破产", "重组失败",
        "decline", "loss", "lawsuit", "penalty", "default",
        "warning", "investigation", "delisting", "risk",
    ]

    DEFAULT_POSITIVE_ANNOUNCEMENT_TYPES: List[str] = [
        "回购", "增持", "分红", "送转", "业绩预增", "重大合同",
        "中标", "资产注入", "并购重组", "新产品", "专利",
        "ipo", "增发", "股权激励", "战略合作", "分红派息",
    ]

    DEFAULT_NEGATIVE_ANNOUNCEMENT_TYPES: List[str] = [
        "减持", "诉讼", "处罚", "退市风险", "业绩预亏",
        "债务违约", "商誉减值", "质押", "冻结", "立案调查",
        "停产", "停工", "终止重组", "警示函", "监管函",
        "st", "退市", "破产", "清算", "担保", "违规",
    ]

    def __init__(self, config_dir: str = "config") -> None:
        """Initialize the research analyzer.

        Args:
            config_dir: Path to configuration directory.
        """
        config = get_config(config_dir)
        self._config = config
        self._event_bus = get_event_bus()
        self._audit = get_audit_logger()

        # Load keyword dictionaries from config
        self._positive_keywords: List[str] = config.get(
            "research.positive_keywords", self.DEFAULT_POSITIVE_KEYWORDS
        )
        self._negative_keywords: List[str] = config.get(
            "research.negative_keywords", self.DEFAULT_NEGATIVE_KEYWORDS
        )
        self._positive_announcement_types: List[str] = config.get(
            "research.positive_announcement_types",
            self.DEFAULT_POSITIVE_ANNOUNCEMENT_TYPES,
        )
        self._negative_announcement_types: List[str] = config.get(
            "research.negative_announcement_types",
            self.DEFAULT_NEGATIVE_ANNOUNCEMENT_TYPES,
        )

        # Thresholds from config
        self._sentiment_positive_threshold: float = config.get(
            "research.sentiment_positive_threshold", 0.3
        )
        self._sentiment_negative_threshold: float = config.get(
            "research.sentiment_negative_threshold", -0.3
        )
        self._risk_warning_threshold: float = config.get(
            "research.risk_warning_threshold", 0.5
        )

        # Cached summaries per symbol
        self._summaries: Dict[str, ResearchSummary] = {}

        logger.info(
            "ResearchAnalyzer initialized: positive_keywords=%d, "
            "negative_keywords=%d",
            len(self._positive_keywords),
            len(self._negative_keywords),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_news(
        self, symbol: str, news_data: List[Dict[str, Any]]
    ) -> NewsSentimentResult:
        """Analyze news sentiment for a symbol using keyword-based NLP.

        Args:
            symbol: Stock symbol (e.g., '600519').
            news_data: List of news article dicts. Each dict may contain:
                - title: article title
                - content: article body text (optional)
                - source: news source
                - published_at: publication timestamp
                - url: source URL (optional)

        Returns:
            NewsSentimentResult with overall sentiment score and breakdown.

        Raises:
            ValueError: If symbol is empty.
        """
        if not symbol:
            raise ValueError("symbol must not be empty")

        if not isinstance(news_data, list):
            news_data = []

        if not news_data:
            logger.warning("Empty news data for %s, returning neutral", symbol)
            result = NewsSentimentResult(
                symbol=symbol,
                overall_score=0.0,
                sentiment_label="neutral",
                article_count=0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                confidence=0.0,
                analyzed_at=datetime.now().isoformat(),
            )
            self._cache_and_publish_news(symbol, result)
            return result

        positive_count = 0
        negative_count = 0
        neutral_count = 0
        all_keywords: List[str] = []
        scores: List[float] = []

        for article in news_data:
            if not isinstance(article, dict):
                continue

            title = str(article.get("title", ""))
            content = str(article.get("content", ""))
            combined_text = title + " " + content

            if not combined_text.strip():
                neutral_count += 1
                scores.append(0.0)
                continue

            pos_hits = self._count_keywords(combined_text, self._positive_keywords)
            neg_hits = self._count_keywords(combined_text, self._negative_keywords)

            for kw, cnt in pos_hits.items():
                all_keywords.extend([kw] * cnt)
            for kw, cnt in neg_hits.items():
                all_keywords.extend([kw] * cnt)

            total_pos = sum(pos_hits.values())
            total_neg = sum(neg_hits.values())

            if total_pos + total_neg == 0:
                neutral_count += 1
                scores.append(0.0)
            else:
                article_score = (total_pos - total_neg) / (total_pos + total_neg)
                scores.append(article_score)

                if article_score > self._sentiment_positive_threshold:
                    positive_count += 1
                elif article_score < self._sentiment_negative_threshold:
                    negative_count += 1
                else:
                    neutral_count += 1

        overall_score = float(np.mean(scores)) if scores else 0.0

        if overall_score >= self._sentiment_positive_threshold:
            sentiment_label = "positive"
        elif overall_score <= self._sentiment_negative_threshold:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"

        keyword_counter = Counter(all_keywords)
        key_keywords = [kw for kw, _ in keyword_counter.most_common(10)]

        confidence = min(1.0, len(scores) / 10.0)

        result = NewsSentimentResult(
            symbol=symbol,
            overall_score=round(overall_score, 4),
            sentiment_label=sentiment_label,
            article_count=len(scores),
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            key_keywords=key_keywords,
            confidence=round(confidence, 4),
            analyzed_at=datetime.now().isoformat(),
        )

        self._cache_and_publish_news(symbol, result)
        return result

    def analyze_announcements(
        self, symbol: str, announcements: List[Dict[str, Any]]
    ) -> AnnouncementResult:
        """Scan and classify company announcements.

        Args:
            symbol: Stock symbol (e.g., '600519').
            announcements: List of announcement dicts. Each dict may contain:
                - title: announcement title
                - type: announcement type/category
                - content: full text (optional)
                - published_at: publication date
                - url: source URL (optional)

        Returns:
            AnnouncementResult with classified events and risk warnings.

        Raises:
            ValueError: If symbol is empty.
        """
        if not symbol:
            raise ValueError("symbol must not be empty")

        if not isinstance(announcements, list):
            announcements = []

        if not announcements:
            logger.warning("Empty announcements data for %s, returning neutral", symbol)
            result = AnnouncementResult(
                symbol=symbol,
                total_announcements=0,
                overall_impact="neutral",
                confidence=0.0,
                analyzed_at=datetime.now().isoformat(),
            )
            self._cache_and_publish_announcement(symbol, result)
            return result

        positive_events: List[Dict[str, Any]] = []
        negative_events: List[Dict[str, Any]] = []
        risk_warnings: List[Dict[str, Any]] = []
        neutral_count = 0

        for ann in announcements:
            if not isinstance(ann, dict):
                continue

            title = str(ann.get("title", ""))
            ann_type = str(ann.get("type", ""))
            content = str(ann.get("content", ""))
            published_at = str(ann.get("published_at", ""))

            combined = title + " " + ann_type + " " + content
            if not combined.strip():
                neutral_count += 1
                continue

            # Classify by type keywords first
            is_positive = self._matches_any(
                combined, self._positive_announcement_types
            )
            is_negative = self._matches_any(
                combined, self._negative_announcement_types
            )

            # Fall back to keyword sentiment
            if not is_positive and not is_negative:
                pos_hits = sum(
                    self._count_keywords(
                        combined, self._positive_keywords
                    ).values()
                )
                neg_hits = sum(
                    self._count_keywords(
                        combined, self._negative_keywords
                    ).values()
                )
                if pos_hits > neg_hits:
                    is_positive = True
                elif neg_hits > pos_hits:
                    is_negative = True

            event_entry = {
                "title": title,
                "type": ann_type,
                "published_at": published_at,
                "url": ann.get("url", ""),
            }

            if is_positive:
                positive_events.append(event_entry)
            elif is_negative:
                negative_events.append(event_entry)
                risk_score = self._calculate_risk_score(combined)
                if risk_score >= self._risk_warning_threshold:
                    risk_warnings.append({
                        "title": title,
                        "type": ann_type,
                        "risk_score": round(risk_score, 4),
                        "published_at": published_at,
                        "reason": self._extract_risk_reason(combined),
                    })
            else:
                neutral_count += 1

        total = len(positive_events) + len(negative_events) + neutral_count

        # Determine overall impact
        if len(positive_events) > len(negative_events):
            delta = len(positive_events) - len(negative_events)
            overall_impact = "positive" if delta >= 3 else "neutral"
        elif len(negative_events) > len(positive_events):
            delta = len(negative_events) - len(positive_events)
            overall_impact = "negative" if delta >= 3 else "neutral"
        else:
            overall_impact = "neutral"

        confidence = min(1.0, total / 5.0) if total > 0 else 0.0

        result = AnnouncementResult(
            symbol=symbol,
            total_announcements=total,
            positive_events=positive_events,
            negative_events=negative_events,
            risk_warnings=risk_warnings,
            positive_count=len(positive_events),
            negative_count=len(negative_events),
            neutral_count=neutral_count,
            overall_impact=overall_impact,
            confidence=round(confidence, 4),
            analyzed_at=datetime.now().isoformat(),
        )

        self._cache_and_publish_announcement(symbol, result)
        return result

    def get_summary(self, symbol: str) -> Optional[ResearchSummary]:
        """Get the complete research summary for a symbol.

        Combines news sentiment and announcement analysis into a single
        research summary with key findings and risk warnings.

        Args:
            symbol: Stock symbol.

        Returns:
            ResearchSummary if available, None if no analysis has been
            performed for this symbol.

        Raises:
            ValueError: If symbol is empty.
        """
        if not symbol:
            raise ValueError("symbol must not be empty")

        summary = self._summaries.get(symbol)
        if summary is None:
            logger.warning("No research summary available for %s", symbol)
            return None

        return summary

    def get_all_summaries(self) -> Dict[str, ResearchSummary]:
        """Get all cached research summaries.

        Returns:
            Dict mapping symbol to ResearchSummary.
        """
        return dict(self._summaries)

    # ------------------------------------------------------------------
    # Keyword Matching
    # ------------------------------------------------------------------

    def _count_keywords(
        self, text: str, keywords: List[str]
    ) -> Dict[str, int]:
        """Count occurrences of each keyword in text (case-insensitive)."""
        counts: Dict[str, int] = {}
        lower_text = text.lower()
        for kw in keywords:
            cnt = lower_text.count(kw.lower())
            if cnt > 0:
                counts[kw] = cnt
        return counts

    @staticmethod
    def _matches_any(text: str, patterns: List[str]) -> bool:
        """Check if text matches any pattern (case-insensitive substring)."""
        lower_text = text.lower()
        return any(p.lower() in lower_text for p in patterns)

    def _calculate_risk_score(self, text: str) -> float:
        """Calculate a risk score (0-1) based on negative keyword density."""
        if not text.strip():
            return 0.0

        neg_hits = self._count_keywords(text, self._negative_keywords)
        total_neg = sum(neg_hits.values())

        normalized = min(1.0, total_neg / 5.0)

        # Boost for high-severity keywords
        high_severity = {"破产", "退市", "清算", "立案", "调查", "bankruptcy", "delisting"}
        for kw in high_severity:
            if kw.lower() in text.lower():
                normalized = min(1.0, normalized + 0.3)

        return round(normalized, 4)

    def _extract_risk_reason(self, text: str) -> str:
        """Extract a concise reason for risk classification."""
        found = [kw for kw in self._negative_keywords if kw.lower() in text.lower()]
        if not found:
            return "Multiple risk indicators detected"
        return f"Risk keywords: {', '.join(found[:5])}"

    # ------------------------------------------------------------------
    # Caching and Event Publishing
    # ------------------------------------------------------------------

    def _cache_and_publish_news(
        self, symbol: str, result: NewsSentimentResult
    ) -> None:
        """Cache news sentiment result and publish event."""
        self._update_summary(symbol, news_result=result)

        self._audit.log(
            "research_analysis",
            check_id=f"news_{symbol}",
            result="OK",
            actor="research_analyzer",
            payload={
                "symbol": symbol,
                "sentiment": result.sentiment_label,
                "score": result.overall_score,
                "article_count": result.article_count,
            },
        )

        self._event_bus.publish(
            "research.analysis_complete",
            {
                "type": "news_sentiment",
                "symbol": symbol,
                "sentiment_label": result.sentiment_label,
                "overall_score": result.overall_score,
                "confidence": result.confidence,
                "analyzed_at": result.analyzed_at,
            },
            source="research.analyzer",
        )

        logger.info(
            "News analysis complete for %s: %s (score=%.3f, %d articles)",
            symbol,
            result.sentiment_label,
            result.overall_score,
            result.article_count,
        )

    def _cache_and_publish_announcement(
        self, symbol: str, result: AnnouncementResult
    ) -> None:
        """Cache announcement result and publish event."""
        self._update_summary(symbol, announcement_result=result)

        self._audit.log(
            "research_analysis",
            check_id=f"announcements_{symbol}",
            result="OK",
            actor="research_analyzer",
            payload={
                "symbol": symbol,
                "impact": result.overall_impact,
                "positive": result.positive_count,
                "negative": result.negative_count,
                "risk_warnings": len(result.risk_warnings),
            },
        )

        self._event_bus.publish(
            "research.analysis_complete",
            {
                "type": "announcements",
                "symbol": symbol,
                "overall_impact": result.overall_impact,
                "positive_count": result.positive_count,
                "negative_count": result.negative_count,
                "risk_warning_count": len(result.risk_warnings),
                "confidence": result.confidence,
                "analyzed_at": result.analyzed_at,
            },
            source="research.analyzer",
        )

        logger.info(
            "Announcement analysis complete for %s: %s "
            "(pos=%d, neg=%d, warnings=%d)",
            symbol,
            result.overall_impact,
            result.positive_count,
            result.negative_count,
            len(result.risk_warnings),
        )

    def _update_summary(
        self,
        symbol: str,
        news_result: Optional[NewsSentimentResult] = None,
        announcement_result: Optional[AnnouncementResult] = None,
    ) -> ResearchSummary:
        """Update or create the aggregated research summary."""
        summary = self._summaries.get(symbol)
        if summary is None:
            summary = ResearchSummary(symbol=symbol)

        if news_result is not None:
            summary.news_sentiment = news_result
        if announcement_result is not None:
            summary.announcement_result = announcement_result

        summary.key_findings = self._build_key_findings(summary)
        summary.risk_warnings = self._build_risk_warnings(summary)
        summary.overall_score = self._compute_overall_score(summary)

        if summary.overall_score >= self._sentiment_positive_threshold:
            summary.overall_label = "positive"
        elif summary.overall_score <= self._sentiment_negative_threshold:
            summary.overall_label = "negative"
        else:
            summary.overall_label = "neutral"

        confidences = []
        if summary.news_sentiment is not None:
            confidences.append(summary.news_sentiment.confidence)
        if summary.announcement_result is not None:
            confidences.append(summary.announcement_result.confidence)
        summary.confidence = (
            round(float(np.mean(confidences)), 4) if confidences else 0.0
        )

        summary.generated_at = datetime.now().isoformat()
        self._summaries[symbol] = summary
        return summary

    def _build_key_findings(self, summary: ResearchSummary) -> List[Dict[str, Any]]:
        """Build key findings list from news and announcements."""
        findings: List[Dict[str, Any]] = []

        ns = summary.news_sentiment
        if ns is not None and ns.article_count > 0:
            findings.append({
                "source": "news_sentiment",
                "finding": (
                    f"News sentiment: {ns.sentiment_label} "
                    f"(score={ns.overall_score:.2f}) "
                    f"across {ns.article_count} articles"
                ),
                "confidence": ns.confidence,
                "top_keywords": ns.key_keywords,
            })

        ar = summary.announcement_result
        if ar is not None and ar.total_announcements > 0:
            if ar.positive_events:
                findings.append({
                    "source": "announcements",
                    "finding": (
                        f"{len(ar.positive_events)} positive "
                        f"announcement(s) detected"
                    ),
                    "confidence": ar.confidence,
                    "samples": [e["title"] for e in ar.positive_events[:3]],
                })
            if ar.negative_events:
                findings.append({
                    "source": "announcements",
                    "finding": (
                        f"{len(ar.negative_events)} negative "
                        f"announcement(s) detected"
                    ),
                    "confidence": ar.confidence,
                    "samples": [e["title"] for e in ar.negative_events[:3]],
                })

        return findings

    def _build_risk_warnings(
        self, summary: ResearchSummary
    ) -> List[Dict[str, Any]]:
        """Build risk warnings list."""
        warnings: List[Dict[str, Any]] = []

        ar = summary.announcement_result
        if ar is not None:
            for rw in ar.risk_warnings:
                warnings.append({
                    "source": "announcement",
                    "title": rw.get("title", ""),
                    "risk_score": rw.get("risk_score", 0.0),
                    "reason": rw.get("reason", ""),
                    "published_at": rw.get("published_at", ""),
                })

        ns = summary.news_sentiment
        if (
            ns is not None
            and ns.sentiment_label == "negative"
            and ns.overall_score <= -0.5
        ):
            warnings.append({
                "source": "news_sentiment",
                "title": "Strongly negative news sentiment",
                "risk_score": abs(ns.overall_score),
                "reason": (
                    f"Overall news score {ns.overall_score:.2f} "
                    f"({ns.negative_count}/{ns.article_count} articles negative)"
                ),
                "published_at": ns.analyzed_at,
            })

        return warnings

    def _compute_overall_score(self, summary: ResearchSummary) -> float:
        """Compute the overall research score from news and announcements."""
        scores: List[float] = []
        weights: List[float] = []

        if summary.news_sentiment is not None:
            scores.append(summary.news_sentiment.overall_score)
            weights.append(summary.news_sentiment.confidence)

        if summary.announcement_result is not None:
            ar = summary.announcement_result
            if ar.total_announcements > 0:
                if ar.overall_impact == "positive":
                    impact_score = 0.5 + 0.5 * min(
                        1.0, ar.positive_count / max(ar.total_announcements, 1)
                    )
                elif ar.overall_impact == "negative":
                    impact_score = -0.5 - 0.5 * min(
                        1.0, ar.negative_count / max(ar.total_announcements, 1)
                    )
                else:
                    impact_score = 0.0
                scores.append(impact_score)
                weights.append(ar.confidence)

        if not scores:
            return 0.0

        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        return round(float(np.average(scores, weights=weights)), 4)