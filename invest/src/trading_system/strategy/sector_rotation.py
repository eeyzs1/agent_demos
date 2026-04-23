
import pandas as pd

from trading_system.strategy.base import Signal, SignalType, StrategyBase


class SectorRotationStrategy(StrategyBase):
    def __init__(
        self,
        name: str = "sector_rotation",
        lookback: int = 20,
        top_sectors: int = 3,
        min_sector_heat: float = 60.0,
        min_volume_ratio: float = 1.2,
    ):
        super().__init__(name=name)
        self._lookback = lookback
        self._top_sectors = top_sectors
        self._min_sector_heat = min_sector_heat
        self._min_volume_ratio = min_volume_ratio

    def generate_signals(self, data: pd.DataFrame, **kwargs) -> list[Signal]:
        sector_data = kwargs.get("sector_data")
        if sector_data is None or data.empty:
            return []

        signals = []
        hot_sectors = self._identify_hot_sectors(sector_data)
        if not hot_sectors:
            return signals

        close = data["close"]
        volume = data["volume"]

        if len(close) < self._lookback:
            return signals

        ma_short = close.rolling(window=min(5, len(close))).mean()
        ma_long = close.rolling(window=min(self._lookback, len(close))).mean()
        vol_ma = volume.rolling(window=min(20, len(volume))).mean()

        current_price = close.iloc[-1]
        current_ma_short = ma_short.iloc[-1]
        current_ma_long = ma_long.iloc[-1]
        current_vol = volume.iloc[-1]
        current_vol_ma = vol_ma.iloc[-1] if not pd.isna(vol_ma.iloc[-1]) else current_vol

        volume_ratio = current_vol / current_vol_ma if current_vol_ma > 0 else 1.0

        in_hot_sector = kwargs.get("in_hot_sector", True)

        if in_hot_sector and current_ma_short > current_ma_long and volume_ratio >= self._min_volume_ratio:
            atr = self._calc_atr(data)
            signals.append(Signal(
                symbol=kwargs.get("symbol", ""),
                signal_type=SignalType.BUY,
                price=current_price,
                stop_loss=current_price - atr * 2 if atr > 0 else current_price * 0.95,
                take_profit=current_price + atr * 3 if atr > 0 else current_price * 1.10,
                strategy_name=self.name,
                confidence=min(0.6 + len(hot_sectors) * 0.05, 0.9),
            ))

        if current_ma_short < current_ma_long:
            signals.append(Signal(
                symbol=kwargs.get("symbol", ""),
                signal_type=SignalType.SELL,
                price=current_price,
                strategy_name=self.name,
                confidence=0.6,
            ))

        return signals

    def _identify_hot_sectors(self, sector_data: pd.DataFrame) -> list[str]:
        if sector_data.empty:
            return []

        hot = []
        if "heat_score" in sector_data.columns:
            top = sector_data.nlargest(self._top_sectors, "heat_score")
            hot = top[top["heat_score"] >= self._min_sector_heat]["name"].tolist()
        elif "change_pct" in sector_data.columns:
            top = sector_data.nlargest(self._top_sectors, "change_pct")
            hot = top["name"].tolist()

        return hot

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
            "type": "sector_rotation",
            "description": "板块轮动选股策略：识别强势板块中的龙头股",
            "suitable_markets": ["trending"],
            "params": {
                "lookback": self._lookback,
                "top_sectors": self._top_sectors,
                "min_sector_heat": self._min_sector_heat,
                "min_volume_ratio": self._min_volume_ratio,
            },
        }
