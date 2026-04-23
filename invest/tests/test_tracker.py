from datetime import datetime, timedelta

from trading_system.advisor.tracker import RecommendationTracker


class TestRecommendationTracker:
    def setup_method(self):
        self.tracker = RecommendationTracker()

    def test_record_recommendation(self):
        rec = self.tracker.record_recommendation(
            symbol="600519",
            name="贵州茅台",
            recommendation_type="买入",
            price=100.0,
            score=70.0,
            rating="强推",
            reasons=["技术面向好", "资金流入"],
        )
        assert rec.id.startswith("REC-")
        assert rec.symbol == "600519"
        assert rec.price == 100.0
        assert len(rec.reasons) == 2

    def test_multiple_records(self):
        self.tracker.record_recommendation(symbol="600519", price=100.0, recommendation_type="买入")
        self.tracker.record_recommendation(symbol="000001", price=50.0, recommendation_type="买入")
        assert len(self.tracker.records) == 2

    def test_update_returns(self):
        rec = self.tracker.record_recommendation(
            symbol="600519", price=100.0, recommendation_type="买入"
        )
        rec.created_at = datetime.now() - timedelta(days=5)
        self.tracker.update_returns("600519", {"600519": 110.0})
        assert rec.return_5d is not None
        assert rec.return_5d == 10.0

    def test_get_stats_empty(self):
        stats = self.tracker.get_stats()
        assert stats.total_recommendations == 0

    def test_get_stats_with_records(self):
        rec1 = self.tracker.record_recommendation(
            symbol="600519", price=100.0, recommendation_type="买入", rating="强推"
        )
        rec1.created_at = datetime.now() - timedelta(days=5)
        rec1.return_5d = 5.0

        rec2 = self.tracker.record_recommendation(
            symbol="000001", price=50.0, recommendation_type="买入", rating="推荐"
        )
        rec2.created_at = datetime.now() - timedelta(days=5)
        rec2.return_5d = -2.0

        stats = self.tracker.get_stats()
        assert stats.total_recommendations == 2
        assert stats.accurate_count == 1

    def test_generate_performance_report(self):
        self.tracker.record_recommendation(
            symbol="600519", price=100.0, recommendation_type="买入", rating="强推"
        )
        report = self.tracker.generate_performance_report()
        assert "推荐绩效报告" in report
        assert "总推荐数" in report

    def test_record_to_dict(self):
        rec = self.tracker.record_recommendation(
            symbol="600519", price=100.0, recommendation_type="买入"
        )
        d = rec.to_dict()
        assert "id" in d
        assert "symbol" in d
        assert "price" in d
