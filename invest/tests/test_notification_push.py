from unittest.mock import MagicMock

from trading_system.advisor.daily_report import DailyReportGenerator
from trading_system.advisor.entry_exit import EntryExitAdvisor
from trading_system.scorer.engine import Rating, StockScore, StockScorer


class TestDailyReportNotification:
    def test_no_notification_without_manager(self):
        generator = DailyReportGenerator(output_dir="./tmp_test_output")
        scores = [StockScore(symbol="600519", name="贵州茅台", total_score=70.0, rating=Rating.STRONG_BUY, rank=1)]
        content = generator.generate_report(scores, [])
        assert "A股智能推荐日报" in content

    def test_notification_pushed_with_manager(self):
        mock_manager = MagicMock()
        generator = DailyReportGenerator(
            output_dir="./tmp_test_output",
            notification_manager=mock_manager,
        )
        scorer = StockScorer()
        advisor = EntryExitAdvisor(scorer)
        scores = [StockScore(symbol="600519", name="贵州茅台", total_score=70.0, rating=Rating.STRONG_BUY, rank=1)]
        recs = [advisor.recommend_entry("600519", 100.0, {
            "rsi": 35, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.1,
            "pe_ttm": 10, "pb": 0.8, "roe": 25, "revenue_growth": 30,
            "north_net_inflow": 200, "main_net_inflow": 80, "on_dragon_tiger": True,
            "news_sentiment": 0.4, "sector_heat": 80, "market_mood": 70,
        })]
        generator.generate_report(scores, recs)
        assert mock_manager.notify.called

    def test_urgent_notification(self):
        mock_manager = MagicMock()
        generator = DailyReportGenerator(
            output_dir="./tmp_test_output",
            notification_manager=mock_manager,
        )
        generator.push_urgent_notification("止损触发", "600519 已触发止损")
        assert mock_manager.notify.called
        call_args = mock_manager.notify.call_args[0][0]
        assert "止损触发" in call_args.title

    def test_urgent_notification_no_manager(self):
        generator = DailyReportGenerator(output_dir="./tmp_test_output")
        generator.push_urgent_notification("test", "test")
