import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from trading_system.data.store import DataStore
from trading_system.strategy.aggregator import AggregatedSignal, SignalAggregator
from trading_system.strategy.base import SignalType
from trading_system.strategy.strategies import (
    BreakoutStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
)

logger = logging.getLogger(__name__)

STOCK_STRATEGIES = {
    "trend_following": TrendFollowingStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
}


@dataclass
class FusionDecision:
    symbol: str
    name: str
    price: float
    scorer_score: float
    scorer_rating: str
    strategy_signal: Optional[str] = None
    strategy_consensus: str = "no_signal"
    agreeing_strategies: list[str] = field(default_factory=list)
    disagreeing_strategies: list[str] = field(default_factory=list)
    fusion_confidence: float = 0.0
    fusion_action: str = "HOLD"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    data: dict = field(default_factory=dict)
    aggregated_signals: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": self.price,
            "scorer_score": self.scorer_score,
            "scorer_rating": self.scorer_rating,
            "strategy_signal": self.strategy_signal,
            "strategy_consensus": self.strategy_consensus,
            "agreeing_strategies": self.agreeing_strategies,
            "disagreeing_strategies": self.disagreeing_strategies,
            "fusion_confidence": round(self.fusion_confidence, 4),
            "fusion_action": self.fusion_action,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }


class DecisionFusionEngine:
    def __init__(self, data_store: Optional[DataStore] = None):
        self._store = data_store or DataStore()
        self._strategies: dict[str, object] = {}
        for name, cls in STOCK_STRATEGIES.items():
            try:
                self._strategies[name] = cls()
            except Exception as e:
                logger.warning("Failed to init strategy '%s': %s", name, e)
        self._aggregator = SignalAggregator(self._strategies)
        logger.info("Fusion engine initialized with %d strategies: %s",
                    len(self._strategies), list(self._strategies.keys()))

    def fuse(
        self,
        stock_scores: list,
        stock_data_list: list,
        top_n: int = 30,
    ) -> list[FusionDecision]:
        data_map = {code: d for code, d in stock_data_list}
        top_stocks = sorted(stock_scores, key=lambda x: x.total_score, reverse=True)[:top_n]

        results = []
        for stock in top_stocks:
            code = stock.symbol
            sdata = data_map.get(code, {})
            price = sdata.get("price", 0)

            agg_signals = []
            try:
                df = self._store.fetch_daily(code, source="akshare", use_cache=True)
                if not df.empty and len(df) >= 30:
                    df = self._ensure_columns(df)
                    agg_signals = self._aggregator.aggregate_signals(df, symbol=code)
            except Exception as e:
                logger.debug("Strategy signals failed for %s: %s", code, str(e)[:80])

            decision = self._build_decision(code, stock, price, sdata, agg_signals)
            results.append(decision)

        results.sort(key=lambda x: x.fusion_confidence, reverse=True)
        logger.info("Fusion complete: %d decisions, %d BUY signals",
                    len(results),
                    sum(1 for r in results if r.fusion_action == "BUY"))
        return results

    def _build_decision(
        self,
        code: str,
        score,
        price: float,
        sdata: dict,
        agg_signals: list[AggregatedSignal],
    ) -> FusionDecision:
        latest_buy = None
        latest_sell = None

        for sig in agg_signals:
            if sig.signal_type == SignalType.BUY:
                if latest_buy is None or sig.strategy_count > latest_buy.strategy_count:
                    latest_buy = sig
            elif sig.signal_type == SignalType.SELL:
                if latest_sell is None or sig.strategy_count > latest_sell.strategy_count:
                    latest_sell = sig

        if latest_buy:
            strategy_signal = "BUY"
            consensus = latest_buy.consensus_strength
            agreeing = latest_buy.agreeing_strategies
            disagreeing = latest_buy.disagreeing_strategies
            sig_stop = latest_buy.original_signals[0].stop_loss if latest_buy.original_signals else None
            sig_tp = latest_buy.original_signals[0].take_profit if latest_buy.original_signals else None
        elif latest_sell:
            strategy_signal = "SELL"
            consensus = latest_sell.consensus_strength
            agreeing = latest_sell.agreeing_strategies
            disagreeing = latest_sell.disagreeing_strategies
            sig_stop = latest_sell.original_signals[0].stop_loss if latest_sell.original_signals else None
            sig_tp = latest_sell.original_signals[0].take_profit if latest_sell.original_signals else None
        else:
            strategy_signal = None
            consensus = "no_signal"
            agreeing = []
            disagreeing = []
            sig_stop = None
            sig_tp = None

        scorer_weight = score.total_score / 100
        strategy_weight = 0.0
        if consensus == "strong":
            strategy_weight = 0.8
        elif consensus == "moderate":
            strategy_weight = 0.5
        elif consensus == "weak":
            strategy_weight = 0.2
        elif strategy_signal:
            strategy_weight = 0.15

        if strategy_signal == "SELL":
            strategy_weight = -strategy_weight

        fusion_confidence = scorer_weight * 0.55 + strategy_weight * 0.45
        fusion_confidence = max(0.0, min(1.0, fusion_confidence))

        if fusion_confidence >= 0.65 and (strategy_signal != "SELL" or scorer_weight > 0.6):
            action = "BUY"
        elif fusion_confidence <= 0.25 or strategy_signal == "SELL":
            action = "SELL"
        else:
            action = "HOLD"

        return FusionDecision(
            symbol=code,
            name=sdata.get("name", ""),
            price=price,
            scorer_score=score.total_score,
            scorer_rating=score.rating.value,
            strategy_signal=strategy_signal,
            strategy_consensus=consensus,
            agreeing_strategies=agreeing,
            disagreeing_strategies=disagreeing,
            fusion_confidence=fusion_confidence,
            fusion_action=action,
            stop_loss=sig_stop,
            take_profit=sig_tp,
            data=sdata,
            aggregated_signals=[s.__dict__ for s in agg_signals],
        )

    @staticmethod
    def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                if col == "volume" and "amount" in df.columns:
                    df["volume"] = df["amount"]
                else:
                    df[col] = df.get("close", 0) if col in ("open", "high", "low") else 0
        return df