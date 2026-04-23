import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from trading_system.strategy.base import Signal, SignalType, StrategyBase

logger = logging.getLogger(__name__)


@dataclass
class AggregatedSignal:
    symbol: str
    signal_type: SignalType
    price: float
    confidence: float
    strategy_count: int
    agreeing_strategies: list[str]
    disagreeing_strategies: list[str]
    original_signals: list[Signal] = field(default_factory=list)

    @property
    def consensus_strength(self) -> str:
        if self.strategy_count >= 3 and self.confidence >= 0.8:
            return "strong"
        if self.strategy_count >= 3 and self.confidence >= 0.6:
            return "strong"
        if self.strategy_count >= 2 and self.confidence >= 0.6:
            return "moderate"
        return "weak"

    @property
    def needs_manual_review(self) -> bool:
        buy_count = len([s for s in self.original_signals if s.signal_type == SignalType.BUY])
        sell_count = len([s for s in self.original_signals if s.signal_type == SignalType.SELL])
        return buy_count > 0 and sell_count > 0


class SignalAggregator:
    def __init__(self, strategies: Optional[dict[str, StrategyBase]] = None):
        self._strategies: dict[str, StrategyBase] = strategies or {}

    def register_strategy(self, name: str, strategy: StrategyBase) -> None:
        self._strategies[name] = strategy

    def aggregate_signals(self, data, symbol: str = "") -> list[AggregatedSignal]:
        all_signals: dict[str, list[tuple[str, Signal]]] = defaultdict(list)

        for name, strategy in self._strategies.items():
            try:
                signals = strategy.generate_signals(data)
                for sig in signals:
                    sig.symbol = symbol
                    ts_val = sig.timestamp
                    if hasattr(ts_val, "date"):
                        ts_key = str(ts_val.date())
                    elif hasattr(ts_val, "isoformat"):
                        ts_key = ts_val.isoformat()[:10]
                    else:
                        ts_key = str(ts_val)[:10]
                    all_signals[ts_key].append((name, sig))
            except Exception as e:
                logger.error("Strategy %s failed to generate signals: %s", name, e)

        aggregated = []
        for ts_key, named_signals in all_signals.items():
            buy_strategies = []
            sell_strategies = []
            buy_signals = []
            sell_signals = []

            for name, sig in named_signals:
                if sig.signal_type == SignalType.BUY:
                    buy_strategies.append(name)
                    buy_signals.append(sig)
                elif sig.signal_type == SignalType.SELL:
                    sell_strategies.append(name)
                    sell_signals.append(sig)

            if buy_signals:
                avg_conf = sum(s.confidence for s in buy_signals) / len(buy_signals)
                if len(buy_strategies) >= 3:
                    final_conf = 0.9
                else:
                    consensus_boost = min(len(buy_strategies) / max(len(self._strategies), 1), 1.0)
                    final_conf = min(avg_conf * (1 + consensus_boost * 0.3), 1.0)

                ref_signal = buy_signals[0]
                aggregated.append(
                    AggregatedSignal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        price=ref_signal.price,
                        confidence=final_conf,
                        strategy_count=len(buy_strategies),
                        agreeing_strategies=buy_strategies,
                        disagreeing_strategies=sell_strategies,
                        original_signals=buy_signals,
                    )
                )

            if sell_signals:
                avg_conf = sum(s.confidence for s in sell_signals) / len(sell_signals)
                if len(sell_strategies) >= 3:
                    final_conf = 0.9
                else:
                    consensus_boost = min(len(sell_strategies) / max(len(self._strategies), 1), 1.0)
                    final_conf = min(avg_conf * (1 + consensus_boost * 0.3), 1.0)

                ref_signal = sell_signals[0]
                aggregated.append(
                    AggregatedSignal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        price=ref_signal.price,
                        confidence=final_conf,
                        strategy_count=len(sell_strategies),
                        agreeing_strategies=sell_strategies,
                        disagreeing_strategies=buy_strategies,
                        original_signals=sell_signals,
                    )
                )

        return aggregated

    def to_signals(self, data, symbol: str = "", min_consensus: str = "weak") -> list[Signal]:
        consensus_order = {"weak": 0, "moderate": 1, "strong": 2}
        min_level = consensus_order.get(min_consensus, 0)

        aggregated = self.aggregate_signals(data, symbol)
        signals = []

        for agg in aggregated:
            if consensus_order.get(agg.consensus_strength, 0) < min_level:
                continue

            ref = agg.original_signals[0] if agg.original_signals else None
            if not ref:
                continue

            stop_loss = ref.stop_loss
            take_profit = ref.take_profit
            for sig in agg.original_signals[1:]:
                if sig.stop_loss is not None:
                    if stop_loss is None:
                        stop_loss = sig.stop_loss
                    elif agg.signal_type == SignalType.BUY:
                        stop_loss = max(stop_loss, sig.stop_loss)
                    else:
                        stop_loss = min(stop_loss, sig.stop_loss)
                if sig.take_profit is not None:
                    if take_profit is None:
                        take_profit = sig.take_profit
                    elif agg.signal_type == SignalType.BUY:
                        take_profit = min(take_profit, sig.take_profit)
                    else:
                        take_profit = max(take_profit, sig.take_profit)

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=agg.signal_type,
                    price=agg.price,
                    timestamp=ref.timestamp,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    r_multiple=ref.r_multiple,
                    confidence=agg.confidence,
                    strategy_name="+".join(agg.agreeing_strategies),
                    market_state=ref.market_state,
                    metadata={
                        "consensus": agg.consensus_strength,
                        "strategy_count": agg.strategy_count,
                        "agreeing": agg.agreeing_strategies,
                        "disagreeing": agg.disagreeing_strategies,
                    },
                )
            )

        return signals
