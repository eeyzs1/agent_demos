from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from trading_system.scorer.engine import Rating, StockScore, StockScorer


class RecommendationType(str, Enum):
    BUY = "买入"
    SELL = "卖出"
    HOLD = "持有"


@dataclass
class TradeRecommendation:
    symbol: str
    name: str = ""
    recommendation_type: RecommendationType = RecommendationType.HOLD
    current_price: float = 0.0
    entry_price_low: Optional[float] = None
    entry_price_high: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_pct: float = 0.0
    score: Optional[StockScore] = None
    reasons: list[str] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    max_drawdown_expect: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "recommendation_type": self.recommendation_type.value,
            "current_price": self.current_price,
            "entry_price_low": self.entry_price_low,
            "entry_price_high": self.entry_price_high,
            "exit_price": self.exit_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_pct": round(self.position_pct, 2),
            "reasons": self.reasons,
            "risk_warnings": self.risk_warnings,
            "confidence": round(self.confidence, 2),
            "max_drawdown_expect": round(self.max_drawdown_expect, 2),
        }


class EntryExitAdvisor:
    def __init__(self, scorer: Optional[StockScorer] = None):
        self._scorer = scorer or StockScorer()

    def recommend_entry(
        self,
        symbol: str,
        current_price: float,
        data: dict,
        atr: float = 0.0,
    ) -> TradeRecommendation:
        score = self._scorer.score(symbol, data)
        reasons = []
        risk_warnings = []

        if score.technical_score > 60:
            reasons.append(f"技术面评分{score.technical_score:.0f}，趋势向好")
        if score.fundamental_score > 60:
            reasons.append(f"基本面评分{score.fundamental_score:.0f}，估值合理")
        if score.capital_score > 60:
            reasons.append(f"资金面评分{score.capital_score:.0f}，资金流入")
        if score.sentiment_score > 60:
            reasons.append(f"情绪面评分{score.sentiment_score:.0f}，市场看好")

        if score.technical_score < 40:
            risk_warnings.append("技术面偏弱，注意趋势风险")
        if score.fundamental_score < 40:
            risk_warnings.append("基本面较差，注意估值风险")
        if score.capital_score < 40:
            risk_warnings.append("资金面流出，注意流动性风险")

        if score.rating in (Rating.STRONG_BUY, Rating.BUY):
            rec_type = RecommendationType.BUY
            stop_loss_pct = 0.05 if score.rating == Rating.STRONG_BUY else 0.07
            take_profit_pct = 0.15 if score.rating == Rating.STRONG_BUY else 0.10

            if atr > 0:
                stop_loss = current_price - atr * 2
                take_profit = current_price + atr * 3
            else:
                stop_loss = current_price * (1 - stop_loss_pct)
                take_profit = current_price * (1 + take_profit_pct)

            entry_low = current_price * 0.98
            entry_high = current_price * 1.01

            position_pct = min(score.total_score / 100 * 0.3, 0.3)
            confidence = score.total_score / 100
            max_dd = stop_loss_pct

            return TradeRecommendation(
                symbol=symbol,
                name=data.get("name", ""),
                recommendation_type=rec_type,
                current_price=current_price,
                entry_price_low=round(entry_low, 2),
                entry_price_high=round(entry_high, 2),
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                position_pct=round(position_pct, 2),
                score=score,
                reasons=reasons,
                risk_warnings=risk_warnings,
                confidence=round(confidence, 2),
                max_drawdown_expect=round(max_dd, 2),
            )

        elif score.rating == Rating.AVOID:
            risk_warnings.append("综合评分低，建议回避")
            return TradeRecommendation(
                symbol=symbol,
                name=data.get("name", ""),
                recommendation_type=RecommendationType.HOLD,
                current_price=current_price,
                score=score,
                reasons=reasons,
                risk_warnings=risk_warnings,
                confidence=round(score.total_score / 100, 2),
            )

        return TradeRecommendation(
            symbol=symbol,
            name=data.get("name", ""),
            recommendation_type=RecommendationType.HOLD,
            current_price=current_price,
            score=score,
            reasons=reasons,
            risk_warnings=risk_warnings,
            confidence=round(score.total_score / 100, 2),
        )

    def recommend_exit(
        self,
        symbol: str,
        current_price: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        trailing_stop: Optional[float] = None,
        data: Optional[dict] = None,
    ) -> TradeRecommendation:
        reasons = []
        risk_warnings = []

        if current_price <= stop_loss:
            reasons.append(f"触发止损：当前价{current_price:.2f} <= 止损价{stop_loss:.2f}")
            rec_type = RecommendationType.SELL
            exit_price = current_price
        elif current_price >= take_profit:
            reasons.append(f"触发止盈：当前价{current_price:.2f} >= 止盈价{take_profit:.2f}")
            rec_type = RecommendationType.SELL
            exit_price = current_price
        elif trailing_stop and current_price <= trailing_stop:
            reasons.append(f"触发追踪止损：当前价{current_price:.2f} <= 追踪止损{trailing_stop:.2f}")
            rec_type = RecommendationType.SELL
            exit_price = current_price
        else:
            rec_type = RecommendationType.HOLD
            exit_price = None
            profit_pct = (current_price - entry_price) / entry_price * 100
            if profit_pct > 5:
                reasons.append(f"当前盈利{profit_pct:.1f}%，可考虑部分止盈")
            elif profit_pct < -3:
                risk_warnings.append(f"当前亏损{profit_pct:.1f}%，注意止损风险")

        return TradeRecommendation(
            symbol=symbol,
            recommendation_type=rec_type,
            current_price=current_price,
            exit_price=round(exit_price, 2) if exit_price else None,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasons=reasons,
            risk_warnings=risk_warnings,
        )
