from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class Rating(str, Enum):
    STRONG_BUY = "强推"
    BUY = "推荐"
    HOLD = "观望"
    AVOID = "回避"


@dataclass
class FactorScore:
    name: str
    score: float
    weight: float
    weighted_score: float
    details: dict = field(default_factory=dict)


@dataclass
class StockScore:
    symbol: str
    name: str = ""
    total_score: float = 0.0
    technical_score: float = 0.0
    fundamental_score: float = 0.0
    capital_score: float = 0.0
    sentiment_score: float = 0.0
    rating: Rating = Rating.HOLD
    rank: int = 0
    factor_scores: list[FactorScore] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "total_score": round(self.total_score, 2),
            "technical_score": round(self.technical_score, 2),
            "fundamental_score": round(self.fundamental_score, 2),
            "capital_score": round(self.capital_score, 2),
            "sentiment_score": round(self.sentiment_score, 2),
            "rating": self.rating.value,
            "rank": self.rank,
        }


FACTOR_WEIGHTS = {
    "technical": 0.40,
    "fundamental": 0.30,
    "capital": 0.20,
    "sentiment": 0.10,
}


class StockScorer:
    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
    ):
        self._weights = weights or FACTOR_WEIGHTS

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def score_technical(self, data: dict) -> FactorScore:
        sub_scores = {}
        rsi = data.get("rsi", 50)
        if rsi <= 30:
            sub_scores["rsi"] = 80
        elif rsi <= 40:
            sub_scores["rsi"] = 70
        elif rsi <= 60:
            sub_scores["rsi"] = 50
        elif rsi <= 70:
            sub_scores["rsi"] = 40
        else:
            sub_scores["rsi"] = 20

        ma_bullish = data.get("ma_bullish", False)
        sub_scores["trend"] = 80 if ma_bullish else 30

        vol_ratio = data.get("volume_ratio", 1.0)
        if vol_ratio >= 2.0:
            sub_scores["volume"] = 80
        elif vol_ratio >= 1.5:
            sub_scores["volume"] = 65
        elif vol_ratio >= 1.0:
            sub_scores["volume"] = 50
        else:
            sub_scores["volume"] = 30

        volatility = data.get("volatility", 0.2)
        if volatility <= 0.15:
            sub_scores["volatility"] = 70
        elif volatility <= 0.25:
            sub_scores["volatility"] = 50
        else:
            sub_scores["volatility"] = 30

        avg_score = np.mean(list(sub_scores.values()))
        weight = self._weights.get("technical", 0.4)
        return FactorScore(
            name="technical",
            score=round(avg_score, 2),
            weight=weight,
            weighted_score=round(avg_score * weight, 2),
            details=sub_scores,
        )

    def score_fundamental(self, data: dict) -> FactorScore:
        sub_scores = {}

        pe = data.get("pe_ttm")
        if pe is None:
            sub_scores["pe"] = 50
        elif pe <= 0:
            sub_scores["pe"] = 10
        elif pe <= 15:
            sub_scores["pe"] = 85
        elif pe <= 25:
            sub_scores["pe"] = 70
        elif pe <= 40:
            sub_scores["pe"] = 50
        else:
            sub_scores["pe"] = 25

        pb = data.get("pb")
        if pb is None:
            sub_scores["pb"] = 50
        elif pb <= 0:
            sub_scores["pb"] = 10
        elif pb <= 1:
            sub_scores["pb"] = 80
        elif pb <= 3:
            sub_scores["pb"] = 65
        elif pb <= 5:
            sub_scores["pb"] = 45
        else:
            sub_scores["pb"] = 25

        roe = data.get("roe")
        if roe is None:
            sub_scores["roe"] = 50
        elif roe >= 20:
            sub_scores["roe"] = 90
        elif roe >= 15:
            sub_scores["roe"] = 75
        elif roe >= 10:
            sub_scores["roe"] = 60
        elif roe >= 5:
            sub_scores["roe"] = 40
        else:
            sub_scores["roe"] = 15

        rev_growth = data.get("revenue_growth")
        if rev_growth is None:
            sub_scores["revenue_growth"] = 50
        elif rev_growth >= 30:
            sub_scores["revenue_growth"] = 90
        elif rev_growth >= 15:
            sub_scores["revenue_growth"] = 70
        elif rev_growth >= 5:
            sub_scores["revenue_growth"] = 55
        elif rev_growth >= 0:
            sub_scores["revenue_growth"] = 40
        else:
            sub_scores["revenue_growth"] = 15

        avg_score = np.mean(list(sub_scores.values()))
        weight = self._weights.get("fundamental", 0.3)
        return FactorScore(
            name="fundamental",
            score=round(avg_score, 2),
            weight=weight,
            weighted_score=round(avg_score * weight, 2),
            details=sub_scores,
        )

    def score_capital(self, data: dict) -> FactorScore:
        sub_scores = {}

        north_flow = data.get("north_net_inflow", 0)
        if north_flow > 100:
            sub_scores["north_flow"] = 85
        elif north_flow > 0:
            sub_scores["north_flow"] = 65
        elif north_flow > -100:
            sub_scores["north_flow"] = 40
        else:
            sub_scores["north_flow"] = 15

        main_inflow = data.get("main_net_inflow", 0)
        if main_inflow > 50:
            sub_scores["main_flow"] = 80
        elif main_inflow > 0:
            sub_scores["main_flow"] = 60
        elif main_inflow > -50:
            sub_scores["main_flow"] = 40
        else:
            sub_scores["main_flow"] = 20

        on_dragon_tiger = data.get("on_dragon_tiger", False)
        sub_scores["dragon_tiger"] = 75 if on_dragon_tiger else 50

        avg_score = np.mean(list(sub_scores.values()))
        weight = self._weights.get("capital", 0.2)
        return FactorScore(
            name="capital",
            score=round(avg_score, 2),
            weight=weight,
            weighted_score=round(avg_score * weight, 2),
            details=sub_scores,
        )

    def score_sentiment(self, data: dict) -> FactorScore:
        sub_scores = {}

        news_sentiment = data.get("news_sentiment", 0)
        if news_sentiment > 0.3:
            sub_scores["news"] = 80
        elif news_sentiment > 0:
            sub_scores["news"] = 60
        elif news_sentiment > -0.3:
            sub_scores["news"] = 40
        else:
            sub_scores["news"] = 20

        sector_heat = data.get("sector_heat", 50)
        sub_scores["sector_heat"] = min(max(sector_heat, 0), 100)

        market_mood = data.get("market_mood", 50)
        sub_scores["market_mood"] = min(max(market_mood, 0), 100)

        avg_score = np.mean(list(sub_scores.values()))
        weight = self._weights.get("sentiment", 0.1)
        return FactorScore(
            name="sentiment",
            score=round(avg_score, 2),
            weight=weight,
            weighted_score=round(avg_score * weight, 2),
            details=sub_scores,
        )

    def score(self, symbol: str, data: dict) -> StockScore:
        tech = self.score_technical(data)
        fund = self.score_fundamental(data)
        cap = self.score_capital(data)
        sent = self.score_sentiment(data)

        total = tech.weighted_score + fund.weighted_score + cap.weighted_score + sent.weighted_score

        if total >= 65:
            rating = Rating.STRONG_BUY
        elif total >= 50:
            rating = Rating.BUY
        elif total >= 35:
            rating = Rating.HOLD
        else:
            rating = Rating.AVOID

        return StockScore(
            symbol=symbol,
            name=data.get("name", ""),
            total_score=round(total, 2),
            technical_score=tech.score,
            fundamental_score=fund.score,
            capital_score=cap.score,
            sentiment_score=sent.score,
            rating=rating,
            factor_scores=[tech, fund, cap, sent],
            details=data,
        )

    def rank_stocks(self, stock_data_list: list[tuple[str, dict]]) -> list[StockScore]:
        scores = []
        for symbol, data in stock_data_list:
            s = self.score(symbol, data)
            scores.append(s)

        scores.sort(key=lambda x: x.total_score, reverse=True)
        for i, s in enumerate(scores, 1):
            s.rank = i

        return scores
