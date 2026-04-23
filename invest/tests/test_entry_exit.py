from trading_system.advisor.entry_exit import EntryExitAdvisor, RecommendationType


class TestEntryExitAdvisor:
    def setup_method(self):
        self.advisor = EntryExitAdvisor()

    def test_recommend_entry_buy(self):
        data = {
            "rsi": 35, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.1,
            "pe_ttm": 10, "pb": 0.8, "roe": 25, "revenue_growth": 30,
            "north_net_inflow": 200, "main_net_inflow": 80, "on_dragon_tiger": True,
            "news_sentiment": 0.4, "sector_heat": 80, "market_mood": 70,
        }
        rec = self.advisor.recommend_entry("600519", 100.0, data)
        assert rec.recommendation_type == RecommendationType.BUY
        assert rec.entry_price_low is not None
        assert rec.entry_price_high is not None
        assert rec.stop_loss is not None
        assert rec.take_profit is not None
        assert rec.stop_loss < 100.0
        assert rec.take_profit > 100.0
        assert len(rec.reasons) > 0

    def test_recommend_entry_hold(self):
        data = {
            "rsi": 50, "ma_bullish": False, "volume_ratio": 1.0, "volatility": 0.2,
            "pe_ttm": 25, "pb": 3, "roe": 8, "revenue_growth": 3,
            "north_net_inflow": 0, "main_net_inflow": 0, "on_dragon_tiger": False,
            "news_sentiment": 0, "sector_heat": 50, "market_mood": 50,
        }
        rec = self.advisor.recommend_entry("000001", 100.0, data)
        assert rec.recommendation_type == RecommendationType.HOLD

    def test_recommend_entry_avoid(self):
        data = {
            "rsi": 85, "ma_bullish": False, "volume_ratio": 0.3, "volatility": 0.5,
            "pe_ttm": -5, "pb": -1, "roe": -15, "revenue_growth": -30,
            "north_net_inflow": -300, "main_net_inflow": -100, "on_dragon_tiger": False,
            "news_sentiment": -0.5, "sector_heat": 10, "market_mood": 10,
        }
        rec = self.advisor.recommend_entry("600123", 100.0, data)
        assert len(rec.risk_warnings) > 0

    def test_recommend_entry_with_atr(self):
        data = {
            "rsi": 35, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.1,
            "pe_ttm": 10, "pb": 0.8, "roe": 25, "revenue_growth": 30,
            "north_net_inflow": 200, "main_net_inflow": 80, "on_dragon_tiger": True,
            "news_sentiment": 0.4, "sector_heat": 80, "market_mood": 70,
        }
        rec = self.advisor.recommend_entry("600519", 100.0, data, atr=3.0)
        assert rec.stop_loss == 94.0
        assert rec.take_profit == 109.0

    def test_recommend_exit_stop_loss(self):
        rec = self.advisor.recommend_exit(
            "600519", 90.0, 100.0, stop_loss=95.0, take_profit=115.0
        )
        assert rec.recommendation_type == RecommendationType.SELL
        assert any("止损" in r for r in rec.reasons)

    def test_recommend_exit_take_profit(self):
        rec = self.advisor.recommend_exit(
            "600519", 120.0, 100.0, stop_loss=95.0, take_profit=115.0
        )
        assert rec.recommendation_type == RecommendationType.SELL
        assert any("止盈" in r for r in rec.reasons)

    def test_recommend_exit_trailing_stop(self):
        rec = self.advisor.recommend_exit(
            "600519", 105.0, 100.0, stop_loss=95.0, take_profit=115.0, trailing_stop=106.0
        )
        assert rec.recommendation_type == RecommendationType.SELL
        assert any("追踪止损" in r for r in rec.reasons)

    def test_recommend_exit_hold(self):
        rec = self.advisor.recommend_exit(
            "600519", 102.0, 100.0, stop_loss=95.0, take_profit=115.0
        )
        assert rec.recommendation_type == RecommendationType.HOLD

    def test_recommendation_to_dict(self):
        data = {
            "rsi": 35, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.1,
            "pe_ttm": 10, "pb": 0.8, "roe": 25, "revenue_growth": 30,
            "north_net_inflow": 200, "main_net_inflow": 80, "on_dragon_tiger": True,
            "news_sentiment": 0.4, "sector_heat": 80, "market_mood": 70,
        }
        rec = self.advisor.recommend_entry("600519", 100.0, data)
        d = rec.to_dict()
        assert "symbol" in d
        assert "recommendation_type" in d
        assert "reasons" in d
