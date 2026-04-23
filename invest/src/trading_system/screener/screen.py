from trading_system.screener.engine import LogicOperator, ScreenCondition, StockScreener


def value_screener() -> StockScreener:
    screener = StockScreener()
    screener.add_conditions([
        ScreenCondition("pe_range", "pe_ttm", "between", (5, 30), LogicOperator.AND),
        ScreenCondition("pb_range", "pb", "between", (0.5, 5), LogicOperator.AND),
        ScreenCondition("roe_min", "roe", ">=", 10, LogicOperator.AND),
        ScreenCondition("revenue_growth_min", "revenue_growth", ">=", 5, LogicOperator.AND),
        ScreenCondition("not_st", "is_st", "==", False, LogicOperator.AND),
    ])
    return screener


def growth_screener() -> StockScreener:
    screener = StockScreener()
    screener.add_conditions([
        ScreenCondition("revenue_growth_high", "revenue_growth", ">=", 20, LogicOperator.AND),
        ScreenCondition("net_profit_growth", "net_profit_growth", ">=", 15, LogicOperator.AND),
        ScreenCondition("roe_min", "roe", ">=", 8, LogicOperator.AND),
        ScreenCondition("not_st", "is_st", "==", False, LogicOperator.AND),
    ])
    return screener


def momentum_screener() -> StockScreener:
    screener = StockScreener()
    screener.add_conditions([
        ScreenCondition("ma_bullish", "ma_bullish", "==", True, LogicOperator.AND),
        ScreenCondition("rsi_oversold", "rsi", "between", (30, 70), LogicOperator.AND),
        ScreenCondition("volume_surge", "volume_ratio", ">=", 1.5, LogicOperator.OR),
        ScreenCondition("price_above_ma20", "price_above_ma20", "==", True, LogicOperator.AND),
        ScreenCondition("not_st", "is_st", "==", False, LogicOperator.AND),
    ])
    return screener


SCREENER_TEMPLATES = {
    "value": value_screener,
    "growth": growth_screener,
    "momentum": momentum_screener,
}


def get_screener(name: str) -> StockScreener:
    if name not in SCREENER_TEMPLATES:
        raise ValueError(f"Unknown screener template: {name}. Available: {list(SCREENER_TEMPLATES.keys())}")
    return SCREENER_TEMPLATES[name]()
