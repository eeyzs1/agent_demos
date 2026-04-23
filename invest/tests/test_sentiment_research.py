
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_index_data():
    dates = pd.date_range(start="2023-01-01", periods=100, freq="B")
    np.random.seed(42)
    close = 3000 + np.cumsum(np.random.randn(100) * 10)
    high = close + np.abs(np.random.randn(100) * 5)
    low = close - np.abs(np.random.randn(100) * 5)
    open_ = close + np.random.randn(100) * 3
    volume = np.random.randint(1e8, 1e9, 100).astype(float)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def sample_sector_data():
    return pd.DataFrame({
        "name": ["半导体", "新能源", "医药", "白酒", "银行", "房地产", "军工", "AI概念"],
        "change_pct": [5.2, 3.8, -1.2, 2.1, 0.5, -2.3, 4.1, 6.8],
        "volume_ratio": [3.2, 2.1, 0.8, 1.5, 0.6, 0.4, 2.8, 4.5],
        "close": [120.5, 85.3, 45.2, 200.1, 10.5, 8.2, 65.3, 150.8],
        "fund_flow": [5e8, 3e8, -1e8, 2e8, 0.5e8, -2e8, 4e8, 8e8],
        "symbols": ["600519,000858", "300750", "600276", "000568", "601398", "000002", "600760", "002230"],
    })


class TestMarketSentimentAnalyzer:
    def test_analyze_with_market_data(self):
        from trading_system.sentiment.analyzer import MarketSentimentAnalyzer, SentimentLevel

        analyzer = MarketSentimentAnalyzer()
        data = {
            "advance_decline": {"advancing": 3000, "declining": 1500},
            "limit_up_down": {"limit_up": 80, "limit_down": 20},
            "turnover_rate": {"rate": 5.0, "avg_rate": 3.0},
            "new_highs_lows": {"new_highs": 50, "new_lows": 10},
            "margin_data": {"balance_change_pct": 2.0},
            "index_trend": {"close": 3100, "prev_close": 3050, "volume": 1e9, "prev_volume": 8e8, "high": 3150, "low": 3040},
        }

        result = analyzer.analyze(data)
        assert 0 <= result.score <= 100
        assert isinstance(result.level, SentimentLevel)
        assert len(result.components) > 0

    def test_analyze_from_index_data(self, sample_index_data):
        from trading_system.sentiment.analyzer import MarketSentimentAnalyzer, SentimentLevel

        analyzer = MarketSentimentAnalyzer()
        result = analyzer.analyze_from_index_data(sample_index_data)

        assert 0 <= result.score <= 100
        assert isinstance(result.level, SentimentLevel)
        assert "index_trend" in result.components

    def test_sentiment_levels(self):
        from trading_system.sentiment.analyzer import SentimentLevel, SentimentResult

        assert SentimentResult.score_to_level(10) == SentimentLevel.EXTREME_FEAR
        assert SentimentResult.score_to_level(30) == SentimentLevel.FEAR
        assert SentimentResult.score_to_level(50) == SentimentLevel.NEUTRAL
        assert SentimentResult.score_to_level(70) == SentimentLevel.GREED
        assert SentimentResult.score_to_level(90) == SentimentLevel.EXTREME_GREED

    def test_empty_data_returns_neutral(self):
        from trading_system.sentiment.analyzer import MarketSentimentAnalyzer, SentimentLevel

        analyzer = MarketSentimentAnalyzer()
        result = analyzer.analyze({})
        assert result.score == 50.0
        assert result.level == SentimentLevel.NEUTRAL

    def test_sentiment_trend(self):
        from trading_system.sentiment.analyzer import MarketSentimentAnalyzer

        analyzer = MarketSentimentAnalyzer()
        for _ in range(5):
            analyzer.analyze({"index_trend": {"close": 3100, "prev_close": 3050}})
        for _ in range(5):
            analyzer.analyze({"index_trend": {"close": 2900, "prev_close": 3050}})

        trend = analyzer.get_trend()
        assert trend["direction"] in ("improving", "deteriorating", "stable")
        assert "change" in trend


class TestHotSpotDetector:
    def test_detect_hot_spots(self, sample_sector_data):
        from trading_system.sentiment.hotspot import HotSpotDetector

        detector = HotSpotDetector()
        spots = detector.detect_hot_spots(sample_sector_data, top_n=5)

        assert len(spots) <= 5
        assert len(spots) > 0
        for spot in spots:
            assert spot.name != ""
            assert spot.score >= 0
            assert spot.momentum in ("climax", "strengthening", "continuing", "emerging", "weakening", "fading")

    def test_hot_spot_persistence(self, sample_sector_data):
        from trading_system.sentiment.hotspot import HotSpotDetector

        detector = HotSpotDetector()
        detector.detect_hot_spots(sample_sector_data)
        detector.detect_hot_spots(sample_sector_data)
        detector.detect_hot_spots(sample_sector_data)

        result = detector.analyze_persistence("AI概念")
        assert "consecutive_days" in result
        assert "score" in result

    def test_sector_rotation(self, sample_sector_data):
        from trading_system.sentiment.hotspot import HotSpotDetector

        detector = HotSpotDetector()
        rotations = detector.detect_sector_rotation(sample_sector_data)

        assert len(rotations) > 0
        for r in rotations:
            assert r.rank >= 1
            assert r.momentum in ("accelerating", "decelerating", "neutral")

    def test_empty_data(self):
        from trading_system.sentiment.hotspot import HotSpotDetector

        detector = HotSpotDetector()
        spots = detector.detect_hot_spots(pd.DataFrame())
        assert spots == []

    def test_momentum_determination(self, sample_sector_data):
        from trading_system.sentiment.hotspot import HotSpotDetector

        detector = HotSpotDetector()
        spots = detector.detect_hot_spots(sample_sector_data)

        momentums = [s.momentum for s in spots]
        assert all(m in ("climax", "strengthening", "continuing", "emerging", "weakening", "fading") for m in momentums)


class TestResearchSources:
    def test_news_item_creation(self):
        from trading_system.research.sources import NewsItem

        item = NewsItem(
            title="测试新闻",
            source="test",
            content="这是一条测试新闻",
            sentiment="positive",
        )
        assert item.title == "测试新闻"
        assert item.sentiment == "positive"

    def test_research_report_creation(self):
        from trading_system.research.sources import ResearchReport

        report = ResearchReport(
            title="测试研报",
            source="test_institute",
            rating="买入",
            target_price=100.0,
        )
        assert report.rating == "买入"
        assert report.target_price == 100.0

    def test_announcement_creation(self):
        from trading_system.research.sources import Announcement

        ann = Announcement(
            title="测试公告",
            symbol="600519",
            ann_type="业绩预告",
            importance="high",
        )
        assert ann.symbol == "600519"
        assert ann.importance == "high"

    def test_aggregator_creation(self):
        from trading_system.research.sources import ResearchDataAggregator

        agg = ResearchDataAggregator()
        assert len(agg._sources) >= 2


class TestResearchEngine:
    def test_research_symbol(self):
        from trading_system.research.engine import ResearchEngine

        engine = ResearchEngine()
        summary = engine.research_symbol("600519")

        assert summary.symbol == "600519"
        assert summary.news_sentiment in ("positive", "negative", "neutral")
        assert isinstance(summary.key_findings, list)
        assert isinstance(summary.risk_warnings, list)

    def test_research_market(self):
        from trading_system.research.engine import ResearchEngine

        engine = ResearchEngine()
        result = engine.research_market()

        assert "timestamp" in result
        assert "hot_spots" in result
        assert "sector_rotations" in result

    def test_news_sentiment_analysis(self):
        from trading_system.research.engine import ResearchEngine
        from trading_system.research.sources import NewsItem

        engine = ResearchEngine()

        positive_news = [
            NewsItem(title="公司业绩大幅增长", source="test", content="利好消息"),
            NewsItem(title="获得重大合同签约", source="test", content="利好"),
        ]
        sentiment = engine._analyze_news_sentiment(positive_news)
        assert sentiment == "positive"

        negative_news = [
            NewsItem(title="公司业绩亏损严重", source="test", content="利空消息"),
            NewsItem(title="高管减持违规处罚", source="test", content="利空"),
        ]
        sentiment = engine._analyze_news_sentiment(negative_news)
        assert sentiment == "negative"

    def test_findings_generation(self):
        from trading_system.research.engine import ResearchEngine, ResearchSummary

        engine = ResearchEngine()
        summary = ResearchSummary(
            symbol="600519",
            news_sentiment="positive",
            news_count=8,
            announcements=[{"title": "重要公告", "importance": "high"}],
            reports=[{"title": "研报", "source": "中信", "rating": "买入"}],
        )
        engine._generate_findings(summary)

        assert len(summary.key_findings) > 0
