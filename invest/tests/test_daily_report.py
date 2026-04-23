from pathlib import Path

from trading_system.advisor.daily_report import DailyReportGenerator
from trading_system.advisor.entry_exit import EntryExitAdvisor
from trading_system.scorer.engine import Rating, StockScore, StockScorer


class TestDailyReportGenerator:
    def setup_method(self):
        self.scorer = StockScorer()
        self.advisor = EntryExitAdvisor(self.scorer)
        self.output_dir = "./tmp_test_output"
        self.generator = DailyReportGenerator(
            scorer=self.scorer,
            advisor=self.advisor,
            output_dir=self.output_dir,
        )

    def test_generate_report_basic(self):
        scores = [
            StockScore(symbol="600519", name="贵州茅台", total_score=70.0,
                       technical_score=65.0, fundamental_score=75.0,
                       capital_score=60.0, sentiment_score=55.0,
                       rating=Rating.STRONG_BUY, rank=1),
            StockScore(symbol="000001", name="平安银行", total_score=50.0,
                       technical_score=45.0, fundamental_score=55.0,
                       capital_score=50.0, sentiment_score=45.0,
                       rating=Rating.BUY, rank=2),
        ]
        content = self.generator.generate_report(scores, [])
        assert "A股智能推荐日报" in content
        assert "600519" in content
        assert "Top 10" in content

    def test_generate_report_with_recommendations(self):
        scores = [
            StockScore(symbol="600519", name="贵州茅台", total_score=70.0,
                       rating=Rating.STRONG_BUY, rank=1),
        ]
        recs = [self.advisor.recommend_entry("600519", 100.0, {
            "rsi": 35, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.1,
            "pe_ttm": 10, "pb": 0.8, "roe": 25, "revenue_growth": 30,
            "north_net_inflow": 200, "main_net_inflow": 80, "on_dragon_tiger": True,
            "news_sentiment": 0.4, "sector_heat": 80, "market_mood": 70,
        })]
        content = self.generator.generate_report(scores, recs)
        assert "买入推荐" in content

    def test_generate_report_with_market_summary(self):
        content = self.generator.generate_report(
            [], [], market_summary={"北向资金": "净流入", "市场情绪": "偏多"}
        )
        assert "市场概览" in content
        assert "北向资金" in content

    def test_generate_report_with_position_checks(self):
        content = self.generator.generate_report(
            [], [], position_checks=[{"symbol": "600519", "status": "持仓中"}]
        )
        assert "持仓检查" in content

    def test_report_file_created(self):
        scores = [
            StockScore(symbol="600519", name="贵州茅台", total_score=70.0,
                       rating=Rating.STRONG_BUY, rank=1),
        ]
        self.generator.generate_report(scores, [])
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = Path(self.output_dir) / f"daily_{date_str}.md"
        assert report_path.exists()
