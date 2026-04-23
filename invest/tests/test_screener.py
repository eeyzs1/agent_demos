import pandas as pd
import pytest

from trading_system.screener.engine import LogicOperator, ScreenCondition, StockScreener
from trading_system.screener.screen import SCREENER_TEMPLATES, get_screener


@pytest.fixture
def sample_stock_data():
    return pd.DataFrame([
        {"symbol": "600519", "name": "贵州茅台", "pe_ttm": 30.5, "pb": 10.2, "roe": 25.3,
         "revenue_growth": 15.0, "net_profit_growth": 12.0, "is_st": False, "rsi": 55,
         "volume_ratio": 1.2, "ma_bullish": True, "price_above_ma20": True},
        {"symbol": "000001", "name": "平安银行", "pe_ttm": 5.5, "pb": 0.6, "roe": 11.0,
         "revenue_growth": 8.0, "net_profit_growth": 6.0, "is_st": False, "rsi": 45,
         "volume_ratio": 0.8, "ma_bullish": False, "price_above_ma20": False},
        {"symbol": "300750", "name": "宁德时代", "pe_ttm": 50.0, "pb": 8.0, "roe": 15.0,
         "revenue_growth": 40.0, "net_profit_growth": 35.0, "is_st": False, "rsi": 65,
         "volume_ratio": 2.0, "ma_bullish": True, "price_above_ma20": True},
        {"symbol": "600123", "name": "ST某某", "pe_ttm": -5.0, "pb": 0.3, "roe": -10.0,
         "revenue_growth": -20.0, "net_profit_growth": -30.0, "is_st": True, "rsi": 25,
         "volume_ratio": 0.5, "ma_bullish": False, "price_above_ma20": False},
    ])


class TestScreenCondition:
    def test_greater_than(self, sample_stock_data):
        cond = ScreenCondition("high_roe", "roe", ">", 10)
        mask = cond.evaluate(sample_stock_data)
        assert mask.sum() == 3

    def test_between(self, sample_stock_data):
        cond = ScreenCondition("pe_range", "pe_ttm", "between", (5, 30))
        mask = cond.evaluate(sample_stock_data)
        assert mask.sum() == 1

    def test_equals(self, sample_stock_data):
        cond = ScreenCondition("not_st", "is_st", "==", False)
        mask = cond.evaluate(sample_stock_data)
        assert mask.sum() == 3

    def test_missing_column(self, sample_stock_data):
        cond = ScreenCondition("missing", "nonexistent", ">", 0)
        mask = cond.evaluate(sample_stock_data)
        assert mask.sum() == 0


class TestStockScreener:
    def test_single_and_condition(self, sample_stock_data):
        screener = StockScreener()
        screener.add_condition(ScreenCondition("not_st", "is_st", "==", False, LogicOperator.AND))
        results = screener.screen(sample_stock_data)
        assert len(results) == 3

    def test_multiple_and_conditions(self, sample_stock_data):
        screener = StockScreener()
        screener.add_conditions([
            ScreenCondition("not_st", "is_st", "==", False, LogicOperator.AND),
            ScreenCondition("pe_range", "pe_ttm", "between", (5, 35), LogicOperator.AND),
            ScreenCondition("roe_min", "roe", ">=", 10, LogicOperator.AND),
        ])
        results = screener.screen(sample_stock_data)
        assert len(results) == 2
        symbols = [r.symbol for r in results]
        assert "600519" in symbols
        assert "000001" in symbols

    def test_or_conditions(self, sample_stock_data):
        screener = StockScreener()
        screener.add_conditions([
            ScreenCondition("volume_surge", "volume_ratio", ">=", 1.5, LogicOperator.OR),
            ScreenCondition("rsi_low", "rsi", "<=", 30, LogicOperator.OR),
        ])
        results = screener.screen(sample_stock_data)
        assert len(results) >= 1

    def test_empty_conditions(self, sample_stock_data):
        screener = StockScreener()
        results = screener.screen(sample_stock_data)
        assert len(results) == 0

    def test_clear_conditions(self):
        screener = StockScreener()
        screener.add_condition(ScreenCondition("test", "pe", ">", 0))
        screener.clear_conditions()
        assert len(screener.conditions) == 0

    def test_results_sorted_by_score(self, sample_stock_data):
        screener = StockScreener()
        screener.add_conditions([
            ScreenCondition("not_st", "is_st", "==", False, LogicOperator.AND),
            ScreenCondition("roe_min", "roe", ">=", 10, LogicOperator.AND),
        ])
        results = screener.screen(sample_stock_data)
        if len(results) >= 2:
            assert results[0].score >= results[1].score


class TestScreenerTemplates:
    def test_value_screener(self, sample_stock_data):
        screener = get_screener("value")
        results = screener.screen(sample_stock_data)
        assert isinstance(results, list)

    def test_growth_screener(self, sample_stock_data):
        screener = get_screener("growth")
        results = screener.screen(sample_stock_data)
        assert isinstance(results, list)
        symbols = [r.symbol for r in results]
        assert "300750" in symbols

    def test_momentum_screener(self, sample_stock_data):
        screener = get_screener("momentum")
        results = screener.screen(sample_stock_data)
        assert isinstance(results, list)

    def test_unknown_template(self):
        with pytest.raises(ValueError, match="Unknown screener template"):
            get_screener("nonexistent")

    def test_all_templates_available(self):
        assert "value" in SCREENER_TEMPLATES
        assert "growth" in SCREENER_TEMPLATES
        assert "momentum" in SCREENER_TEMPLATES
