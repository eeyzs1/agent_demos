from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np
import pandas as pd


class SentimentLevel(str, Enum):
    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"


@dataclass
class SentimentResult:
    score: float
    level: SentimentLevel
    timestamp: datetime = field(default_factory=datetime.now)
    components: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    @staticmethod
    def score_to_level(score: float) -> SentimentLevel:
        if score <= 20:
            return SentimentLevel.EXTREME_FEAR
        elif score <= 40:
            return SentimentLevel.FEAR
        elif score <= 60:
            return SentimentLevel.NEUTRAL
        elif score <= 80:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED


class MarketSentimentAnalyzer:
    def __init__(self):
        self._history: list[SentimentResult] = []

    def analyze(self, market_data: dict) -> SentimentResult:
        components = {}
        weights = {}

        if "advance_decline" in market_data:
            components["advance_decline"] = self._advance_decline_score(
                market_data["advance_decline"]
            )
            weights["advance_decline"] = 0.20

        if "limit_up_down" in market_data:
            components["limit_up_down"] = self._limit_up_down_score(market_data["limit_up_down"])
            weights["limit_up_down"] = 0.20

        if "turnover_rate" in market_data:
            components["turnover_rate"] = self._turnover_score(market_data["turnover_rate"])
            weights["turnover_rate"] = 0.15

        if "new_highs_lows" in market_data:
            components["new_highs_lows"] = self._new_highs_lows_score(market_data["new_highs_lows"])
            weights["new_highs_lows"] = 0.15

        if "margin_data" in market_data:
            components["margin_data"] = self._margin_score(market_data["margin_data"])
            weights["margin_data"] = 0.15

        if "index_trend" in market_data:
            components["index_trend"] = self._index_trend_score(market_data["index_trend"])
            weights["index_trend"] = 0.15

        if not components:
            return SentimentResult(score=50.0, level=SentimentLevel.NEUTRAL)

        total_weight = sum(weights.get(k, 0.1) for k in components)
        score = (
            sum(components[k] * weights.get(k, 0.1) for k in components) / total_weight
            if total_weight > 0
            else 50.0
        )

        score = max(0, min(100, score))
        level = SentimentResult.score_to_level(score)

        result = SentimentResult(
            score=round(score, 2),
            level=level,
            components=components,
            details=market_data,
        )
        self._history.append(result)
        return result

    def analyze_from_index_data(self, df: pd.DataFrame) -> SentimentResult:
        market_data = {}

        if len(df) >= 2:
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            market_data["index_trend"] = {
                "close": float(latest.get("close", 0)),
                "prev_close": float(prev.get("close", 0)),
                "volume": float(latest.get("volume", 0)),
                "prev_volume": float(prev.get("volume", 0)),
                "high": float(latest.get("high", 0)),
                "low": float(latest.get("low", 0)),
            }

            if len(df) >= 20:
                ma20 = df["close"].rolling(20).mean().iloc[-1]
                market_data["index_trend"]["ma20"] = float(ma20)

            if len(df) >= 5:
                ret_5d = df["close"].pct_change(5).iloc[-1]
                market_data["index_trend"]["return_5d"] = float(ret_5d)

            if len(df) >= 20:
                ret_20d = df["close"].pct_change(20).iloc[-1]
                market_data["index_trend"]["return_20d"] = float(ret_20d)

        return self.analyze(market_data)

    def get_trend(self, window: int = 10) -> dict:
        if len(self._history) < 2:
            return {"direction": "unknown", "change": 0.0}

        recent = self._history[-window:] if len(self._history) >= window else self._history
        scores = [r.score for r in recent]

        if len(scores) < 2:
            return {"direction": "stable", "change": 0.0}

        change = scores[-1] - scores[0]
        if change > 5:
            direction = "improving"
        elif change < -5:
            direction = "deteriorating"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "change": round(change, 2),
            "current": scores[-1],
            "average": round(np.mean(scores), 2),
            "volatility": round(np.std(scores), 2),
        }

    def _advance_decline_score(self, data: dict) -> float:
        advancing = data.get("advancing", 0)
        declining = data.get("declining", 0)
        total = advancing + declining
        if total == 0:
            return 50.0
        ratio = advancing / total
        return ratio * 100

    def _limit_up_down_score(self, data: dict) -> float:
        limit_up = data.get("limit_up", 0)
        limit_down = data.get("limit_down", 0)
        total = limit_up + limit_down
        if total == 0:
            return 50.0
        ratio = limit_up / total
        return ratio * 100

    def _turnover_score(self, data: dict) -> float:
        rate = data.get("rate", 0)
        avg_rate = data.get("avg_rate", 3.0)
        if avg_rate == 0:
            return 50.0
        ratio = rate / avg_rate
        score = min(100, ratio * 50)
        return score

    def _new_highs_lows_score(self, data: dict) -> float:
        new_highs = data.get("new_highs", 0)
        new_lows = data.get("new_lows", 0)
        total = new_highs + new_lows
        if total == 0:
            return 50.0
        ratio = new_highs / total
        return ratio * 100

    def _margin_score(self, data: dict) -> float:
        balance_change = data.get("balance_change_pct", 0)
        score = 50 + balance_change * 10
        return max(0, min(100, score))

    def _index_trend_score(self, data: dict) -> float:
        score = 50.0
        close = data.get("close", 0)
        prev_close = data.get("prev_close", 0)

        if prev_close > 0:
            daily_return = (close - prev_close) / prev_close
            score += daily_return * 500

        ma20 = data.get("ma20")
        if ma20 and ma20 > 0:
            if close > ma20:
                score += 10
            else:
                score -= 10

        ret_5d = data.get("return_5d")
        if ret_5d is not None:
            score += ret_5d * 200

        ret_20d = data.get("return_20d")
        if ret_20d is not None:
            score += ret_20d * 100

        return max(0, min(100, score))
