from trading_system.scorer.engine import FACTOR_WEIGHTS, Rating, StockScorer


class TestStockScorer:
    def setup_method(self):
        self.scorer = StockScorer()

    def test_score_technical_bullish(self):
        data = {"rsi": 45, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.15}
        result = self.scorer.score_technical(data)
        assert result.score > 50
        assert result.weight == FACTOR_WEIGHTS["technical"]

    def test_score_technical_bearish(self):
        data = {"rsi": 80, "ma_bullish": False, "volume_ratio": 0.5, "volatility": 0.4}
        result = self.scorer.score_technical(data)
        assert result.score < 50

    def test_score_fundamental_value(self):
        data = {"pe_ttm": 12, "pb": 0.8, "roe": 22, "revenue_growth": 18}
        result = self.scorer.score_fundamental(data)
        assert result.score > 60

    def test_score_fundamental_poor(self):
        data = {"pe_ttm": -5, "pb": -1, "roe": -10, "revenue_growth": -20}
        result = self.scorer.score_fundamental(data)
        assert result.score < 30

    def test_score_fundamental_missing_data(self):
        data = {}
        result = self.scorer.score_fundamental(data)
        assert result.score == 50

    def test_score_capital_positive_flow(self):
        data = {"north_net_inflow": 200, "main_net_inflow": 100, "on_dragon_tiger": True}
        result = self.scorer.score_capital(data)
        assert result.score > 60

    def test_score_capital_negative_flow(self):
        data = {"north_net_inflow": -200, "main_net_inflow": -100, "on_dragon_tiger": False}
        result = self.scorer.score_capital(data)
        assert result.score < 40

    def test_score_sentiment_positive(self):
        data = {"news_sentiment": 0.5, "sector_heat": 80, "market_mood": 75}
        result = self.scorer.score_sentiment(data)
        assert result.score > 50

    def test_full_score_strong_buy(self):
        data = {
            "rsi": 35, "ma_bullish": True, "volume_ratio": 2.5, "volatility": 0.12,
            "pe_ttm": 10, "pb": 0.8, "roe": 25, "revenue_growth": 30,
            "north_net_inflow": 300, "main_net_inflow": 100, "on_dragon_tiger": True,
            "news_sentiment": 0.5, "sector_heat": 85, "market_mood": 80,
        }
        result = self.scorer.score("600519", data)
        assert result.total_score >= 65
        assert result.rating == Rating.STRONG_BUY

    def test_full_score_avoid(self):
        data = {
            "rsi": 85, "ma_bullish": False, "volume_ratio": 0.3, "volatility": 0.5,
            "pe_ttm": -5, "pb": -1, "roe": -15, "revenue_growth": -30,
            "north_net_inflow": -300, "main_net_inflow": -100, "on_dragon_tiger": False,
            "news_sentiment": -0.5, "sector_heat": 10, "market_mood": 10,
        }
        result = self.scorer.score("600123", data)
        assert result.rating == Rating.AVOID

    def test_full_score_hold(self):
        data = {
            "rsi": 50, "ma_bullish": False, "volume_ratio": 1.0, "volatility": 0.2,
            "pe_ttm": 25, "pb": 3, "roe": 8, "revenue_growth": 3,
            "north_net_inflow": 0, "main_net_inflow": 0, "on_dragon_tiger": False,
            "news_sentiment": 0, "sector_heat": 50, "market_mood": 50,
        }
        result = self.scorer.score("000001", data)
        assert result.rating == Rating.HOLD

    def test_rank_stocks(self):
        stocks = [
            ("600519", {"rsi": 35, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.1,
                        "pe_ttm": 10, "pb": 0.8, "roe": 25, "revenue_growth": 30,
                        "north_net_inflow": 200, "main_net_inflow": 80, "on_dragon_tiger": True,
                        "news_sentiment": 0.4, "sector_heat": 80, "market_mood": 70}),
            ("000001", {"rsi": 50, "ma_bullish": False, "volume_ratio": 1.0, "volatility": 0.2,
                        "pe_ttm": 25, "pb": 3, "roe": 8, "revenue_growth": 3,
                        "north_net_inflow": 0, "main_net_inflow": 0, "on_dragon_tiger": False,
                        "news_sentiment": 0, "sector_heat": 50, "market_mood": 50}),
        ]
        results = self.scorer.rank_stocks(stocks)
        assert len(results) == 2
        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[0].total_score >= results[1].total_score

    def test_stock_score_to_dict(self):
        data = {"rsi": 50, "ma_bullish": True, "volume_ratio": 1.0, "volatility": 0.2}
        result = self.scorer.score("600519", data)
        d = result.to_dict()
        assert "symbol" in d
        assert "total_score" in d
        assert "rating" in d
        assert "rank" in d

    def test_custom_weights(self):
        scorer = StockScorer(weights={"technical": 0.5, "fundamental": 0.3, "capital": 0.1, "sentiment": 0.1})
        data = {"rsi": 35, "ma_bullish": True, "volume_ratio": 2.0, "volatility": 0.1}
        result = scorer.score("600519", data)
        assert result.total_score > 0
