from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from trading_system.research.sources import (
    NewsItem,
    ResearchDataAggregator,
)
from trading_system.sentiment.analyzer import (
    MarketSentimentAnalyzer,
)
from trading_system.sentiment.hotspot import HotSpotDetector


@dataclass
class ResearchSummary:
    symbol: str
    timestamp: datetime = field(default_factory=datetime.now)
    news_sentiment: str = "neutral"
    news_count: int = 0
    top_news: list[dict] = field(default_factory=list)
    reports: list[dict] = field(default_factory=list)
    announcements: list[dict] = field(default_factory=list)
    hot_spots: list[dict] = field(default_factory=list)
    sector_rotations: list[dict] = field(default_factory=list)
    market_sentiment: Optional[dict] = None
    key_findings: list[str] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)


class ResearchEngine:
    def __init__(self):
        self._aggregator = ResearchDataAggregator()
        self._sentiment_analyzer = MarketSentimentAnalyzer()
        self._hotspot_detector = HotSpotDetector()

    def research_symbol(self, symbol: str) -> ResearchSummary:
        summary = ResearchSummary(symbol=symbol)

        news = self._aggregator.fetch_all_news(keyword=symbol, limit=10)
        summary.news_count = len(news)
        summary.top_news = [
            {
                "title": n.title,
                "source": n.source,
                "time": n.publish_time.isoformat() if n.publish_time else "",
                "content": n.content[:200] if n.content else "",
            }
            for n in news[:5]
        ]

        if news:
            summary.news_sentiment = self._analyze_news_sentiment(news)

        reports = self._aggregator.fetch_all_reports(symbol=symbol, limit=5)
        summary.reports = [
            {
                "title": r.title,
                "source": r.source,
                "author": r.author,
                "rating": r.rating,
                "target_price": r.target_price,
            }
            for r in reports
        ]

        announcements = self._aggregator.fetch_all_announcements(symbol=symbol, limit=5)
        summary.announcements = [
            {
                "title": a.title,
                "type": a.ann_type,
                "importance": a.importance,
                "time": a.announce_time.isoformat() if a.announce_time else "",
            }
            for a in announcements
        ]

        self._generate_findings(summary)

        return summary

    def research_market(self) -> dict:
        result = {
            "timestamp": datetime.now().isoformat(),
            "hot_spots": [],
            "sector_rotations": [],
            "sentiment": None,
        }

        sector_data = self._aggregator.fetch_sector_data()
        if not sector_data.empty:
            spots = self._hotspot_detector.detect_hot_spots(sector_data, top_n=10)
            result["hot_spots"] = [
                {
                    "name": s.name,
                    "score": s.score,
                    "change_pct": s.avg_change_pct,
                    "volume_ratio": s.volume_ratio,
                    "consecutive_days": s.consecutive_days,
                    "persistence_score": s.persistence_score,
                    "momentum": s.momentum,
                    "symbols": s.symbols[:5],
                }
                for s in spots
            ]

            rotations = self._hotspot_detector.detect_sector_rotation(sector_data)
            result["sector_rotations"] = [
                {
                    "sector": r.sector,
                    "rank": r.rank,
                    "score": r.score,
                    "change_pct": r.change_pct,
                    "fund_flow": r.fund_flow,
                    "momentum": r.momentum,
                }
                for r in rotations[:10]
            ]

        concept_data = self._aggregator.fetch_concept_sectors()
        if not concept_data.empty:
            concept_spots = self._hotspot_detector.detect_hot_spots(concept_data, top_n=5)
            for s in concept_spots:
                result["hot_spots"].append(
                    {
                        "name": s.name,
                        "score": s.score,
                        "change_pct": s.avg_change_pct,
                        "momentum": s.momentum,
                        "category": "concept",
                    }
                )

        fund_flow = self._aggregator.fetch_fund_flow()
        if not fund_flow.empty:
            top_inflow = fund_flow.nlargest(5, "main_net_inflow")
            result["top_fund_inflow"] = [
                {
                    "symbol": str(row.get("symbol", "")),
                    "name": str(row.get("name", "")),
                    "net_inflow": float(row.get("main_net_inflow", 0)),
                }
                for _, row in top_inflow.iterrows()
            ]

        return result

    def analyze_hot_spot_persistence(self, spot_name: str) -> dict:
        return self._hotspot_detector.analyze_persistence(spot_name)

    def _analyze_news_sentiment(self, news: list[NewsItem]) -> str:
        positive_keywords = [
            "利好",
            "增长",
            "上涨",
            "突破",
            "新高",
            "盈利",
            "超预期",
            "增持",
            "回购",
            "分红",
            "签约",
            "中标",
            "获批",
        ]
        negative_keywords = [
            "利空",
            "下跌",
            "亏损",
            "减持",
            "违规",
            "处罚",
            "退市",
            "暴雷",
            "质押",
            "诉讼",
            "风险",
            "预警",
            "下滑",
        ]
        negation_words = ["不", "未", "无", "非", "没", "莫", "别", "反", "否"]

        pos_score = 0
        neg_score = 0
        for item in news:
            text = item.title + " " + item.content
            for kw in positive_keywords:
                idx = text.find(kw)
                while idx != -1:
                    prefix = text[max(0, idx - 3) : idx]
                    negated = any(nw in prefix for nw in negation_words)
                    if negated:
                        neg_score += 1
                    else:
                        pos_score += 1
                    idx = text.find(kw, idx + len(kw))

            for kw in negative_keywords:
                idx = text.find(kw)
                while idx != -1:
                    prefix = text[max(0, idx - 3) : idx]
                    negated = any(nw in prefix for nw in negation_words)
                    if negated:
                        pos_score += 0.5
                    else:
                        neg_score += 1
                    idx = text.find(kw, idx + len(kw))

        total = len(news)
        if total == 0:
            return "neutral"
        if pos_score > neg_score * 1.5:
            return "positive"
        elif neg_score > pos_score * 1.5:
            return "negative"
        elif pos_score > 0 and neg_score > 0:
            return "mixed"
        else:
            return "neutral"

    def _generate_findings(self, summary: ResearchSummary) -> None:
        if summary.news_sentiment == "positive":
            summary.key_findings.append("📰 新闻情绪偏正面，关注利好消息驱动")
        elif summary.news_sentiment == "negative":
            summary.key_findings.append("⚠️ 新闻情绪偏负面，注意风险")
            summary.risk_warnings.append("新闻面存在利空因素")
        elif summary.news_sentiment == "mixed":
            summary.key_findings.append("🔄 新闻情绪多空交织，需谨慎判断")
            summary.risk_warnings.append("新闻面多空分歧较大")

        if summary.news_count > 5:
            summary.key_findings.append(
                f"📊 近期新闻活跃度高（{summary.news_count}条），市场关注度高"
            )

        for ann in summary.announcements:
            if ann.get("importance") == "high":
                summary.risk_warnings.append(f"重要公告: {ann.get('title', '')}")

        for report in summary.reports:
            rating = report.get("rating", "")
            if "买入" in rating or "增持" in rating:
                summary.key_findings.append(
                    f"📈 研报评级正面: {rating} (来源: {report.get('source', '')})"
                )
            elif "减持" in rating or "卖出" in rating:
                summary.risk_warnings.append(f"研报评级负面: {rating}")

        if not summary.key_findings:
            summary.key_findings.append("暂无明显投研信号")
