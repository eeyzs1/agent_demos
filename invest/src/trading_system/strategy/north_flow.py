
import pandas as pd

from trading_system.strategy.base import Signal, SignalType, StrategyBase


class NorthFlowStrategy(StrategyBase):
    def __init__(
        self,
        name: str = "north_flow",
        consecutive_days: int = 3,
        min_inflow: float = 50.0,
        min_outflow: float = -50.0,
    ):
        super().__init__(name=name)
        self._consecutive_days = consecutive_days
        self._min_inflow = min_inflow
        self._min_outflow = min_outflow

    def generate_signals(self, data: pd.DataFrame, **kwargs) -> list[Signal]:
        north_flow_data = kwargs.get("north_flow_data")
        if data.empty:
            return []

        signals = []
        close = data["close"]

        if len(close) < 2:
            return signals

        current_price = close.iloc[-1]
        atr = self._calc_atr(data)

        if north_flow_data is not None and len(north_flow_data) >= self._consecutive_days:
            recent_flows = north_flow_data[-self._consecutive_days:]

            all_inflow = all(f > self._min_inflow for f in recent_flows)
            all_outflow = all(f < self._min_outflow for f in recent_flows)

            if all_inflow:
                signals.append(Signal(
                    symbol=kwargs.get("symbol", ""),
                    signal_type=SignalType.BUY,
                    price=current_price,
                    stop_loss=current_price - atr * 2 if atr > 0 else current_price * 0.95,
                    take_profit=current_price + atr * 3 if atr > 0 else current_price * 1.10,
                    strategy_name=self.name,
                    confidence=0.7,
                ))
            elif all_outflow:
                signals.append(Signal(
                    symbol=kwargs.get("symbol", ""),
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strategy_name=self.name,
                    confidence=0.7,
                ))

        return signals

    def _calc_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        if len(data) < period:
            return 0.0
        high = data["high"]
        low = data["low"]
        close = data["close"]
        tr = pd.DataFrame({
            "hl": high - low,
            "hc": abs(high - close.shift(1)),
            "lc": abs(low - close.shift(1)),
        }).max(axis=1)
        return float(tr.rolling(window=period).mean().iloc[-1])

    def describe(self) -> dict:
        return {
            "name": self.name,
            "type": "north_flow",
            "description": "北向资金跟随策略：跟踪聪明钱流入流出",
            "suitable_markets": ["trending", "ranging"],
            "params": {
                "consecutive_days": self._consecutive_days,
                "min_inflow": self._min_inflow,
                "min_outflow": self._min_outflow,
            },
        }
