import numpy as np
import pandas as pd

from trading_system.strategy.base import MarketState, Signal, SignalType, StrategyBase
from trading_system.strategy.north_flow import NorthFlowStrategy
from trading_system.strategy.sector_rotation import SectorRotationStrategy


class TrendFollowingStrategy(StrategyBase):
    def __init__(self, params: dict | None = None):
        default_params = {
            "fast_period": 20,
            "slow_period": 50,
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "rr_ratio": 3.0,
            "volume_factor": 1.5,
        }
        if params:
            default_params.update(params)
        super().__init__("trend_following", default_params)

    def generate_signals(self, data: pd.DataFrame) -> list[Signal]:
        if len(data) < self.get_param("slow_period") + 10:
            return []

        df = data.copy()
        fast = self.get_param("fast_period")
        slow = self.get_param("slow_period")
        atr_period = self.get_param("atr_period")
        atr_mult = self.get_param("atr_multiplier")
        rr_ratio = self.get_param("rr_ratio")

        df["sma_fast"] = df["close"].rolling(window=fast).mean()
        df["sma_slow"] = df["close"].rolling(window=slow).mean()
        df["atr"] = self._calculate_atr(df, atr_period)
        df["vol_sma"] = df["volume"].rolling(window=fast).mean()

        signals = []
        for i in range(slow + 1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if pd.isna(row["sma_fast"]) or pd.isna(row["sma_slow"]):
                continue

            bullish_cross = (
                prev["sma_fast"] <= prev["sma_slow"] and row["sma_fast"] > row["sma_slow"]
            )
            bearish_cross = (
                prev["sma_fast"] >= prev["sma_slow"] and row["sma_fast"] < row["sma_slow"]
            )

            volume_confirm = (
                row["volume"] > row["vol_sma"] * self.get_param("volume_factor")
                if not pd.isna(row["vol_sma"])
                else True
            )

            if bullish_cross and volume_confirm:
                stop_loss = row["close"] - row["atr"] * atr_mult
                _, take_profit = self.calculate_r_levels(row["close"], stop_loss, rr_ratio)
                risk = row["close"] - stop_loss
                reward = take_profit - row["close"]
                signals.append(
                    Signal(
                        symbol="",
                        signal_type=SignalType.BUY,
                        price=row["close"],
                        timestamp=df.index[i]
                        if isinstance(df.index[i], pd.Timestamp)
                        else pd.Timestamp.now(),
                        stop_loss=round(stop_loss, 4),
                        take_profit=round(take_profit, 4),
                        r_multiple=round(reward / risk, 2) if risk > 0 else 0,
                        confidence=min(1.0, row["atr"] / row["close"] * 10),
                        strategy_name=self.name,
                        market_state=self.detect_market_state(df.iloc[: i + 1]),
                        metadata={
                            "fast_sma": row["sma_fast"],
                            "slow_sma": row["sma_slow"],
                            "atr": row["atr"],
                        },
                    )
                )

            elif bearish_cross:
                stop_loss = row["close"] + row["atr"] * atr_mult
                _, take_profit = self.calculate_r_levels(row["close"], stop_loss, rr_ratio)
                risk = stop_loss - row["close"]
                reward = row["close"] - take_profit
                signals.append(
                    Signal(
                        symbol="",
                        signal_type=SignalType.SELL,
                        price=row["close"],
                        timestamp=df.index[i]
                        if isinstance(df.index[i], pd.Timestamp)
                        else pd.Timestamp.now(),
                        stop_loss=round(stop_loss, 4),
                        take_profit=round(take_profit, 4),
                        r_multiple=round(reward / risk, 2) if risk > 0 else 0,
                        confidence=min(1.0, row["atr"] / row["close"] * 10),
                        strategy_name=self.name,
                        market_state=self.detect_market_state(df.iloc[: i + 1]),
                        metadata={
                            "fast_sma": row["sma_fast"],
                            "slow_sma": row["sma_slow"],
                            "atr": row["atr"],
                        },
                    )
                )

        return signals

    def describe(self) -> dict:
        return {
            "name": self.name,
            "type": "trend_following",
            "description": "双均线趋势跟踪策略，快线上穿慢线做多，下穿做空",
            "params": self.params,
            "suitable_markets": [MarketState.BULL.value, MarketState.BEAR.value],
        }

    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()


class MeanReversionStrategy(StrategyBase):
    def __init__(self, params: dict | None = None):
        default_params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "rr_ratio": 2.0,
        }
        if params:
            default_params.update(params)
        super().__init__("mean_reversion", default_params)

    def generate_signals(self, data: pd.DataFrame) -> list[Signal]:
        if len(data) < self.get_param("bb_period") + 10:
            return []

        df = data.copy()
        period = self.get_param("bb_period")
        bb_std = self.get_param("bb_std")
        rsi_period = self.get_param("rsi_period")
        rr_ratio = self.get_param("rr_ratio")

        df["sma"] = df["close"].rolling(window=period).mean()
        df["std"] = df["close"].rolling(window=period).std()
        df["upper_band"] = df["sma"] + df["std"] * bb_std
        df["lower_band"] = df["sma"] - df["std"] * bb_std
        df["rsi"] = self._calculate_rsi(df["close"], rsi_period)

        signals = []
        for i in range(period + 1, len(df)):
            row = df.iloc[i]

            if pd.isna(row["rsi"]) or pd.isna(row["lower_band"]):
                continue

            if row["close"] <= row["lower_band"] and row["rsi"] <= self.get_param("rsi_oversold"):
                stop_loss = row["close"] - (row["sma"] - row["lower_band"])
                _, take_profit = self.calculate_r_levels(row["close"], stop_loss, rr_ratio)
                risk = row["close"] - stop_loss
                reward = take_profit - row["close"]
                signals.append(
                    Signal(
                        symbol="",
                        signal_type=SignalType.BUY,
                        price=row["close"],
                        timestamp=df.index[i]
                        if isinstance(df.index[i], pd.Timestamp)
                        else pd.Timestamp.now(),
                        stop_loss=round(stop_loss, 4),
                        take_profit=round(take_profit, 4),
                        r_multiple=round(reward / risk, 2) if risk > 0 else 0,
                        confidence=1.0 - (row["rsi"] / self.get_param("rsi_oversold")),
                        strategy_name=self.name,
                        market_state=self.detect_market_state(df.iloc[: i + 1]),
                        metadata={"rsi": row["rsi"], "bb_position": "lower"},
                    )
                )

            elif row["close"] >= row["upper_band"] and row["rsi"] >= self.get_param(
                "rsi_overbought"
            ):
                stop_loss = row["close"] + (row["upper_band"] - row["sma"])
                _, take_profit = self.calculate_r_levels(row["close"], stop_loss, rr_ratio)
                risk = stop_loss - row["close"]
                reward = row["close"] - take_profit
                signals.append(
                    Signal(
                        symbol="",
                        signal_type=SignalType.SELL,
                        price=row["close"],
                        timestamp=df.index[i]
                        if isinstance(df.index[i], pd.Timestamp)
                        else pd.Timestamp.now(),
                        stop_loss=round(stop_loss, 4),
                        take_profit=round(take_profit, 4),
                        r_multiple=round(reward / risk, 2) if risk > 0 else 0,
                        confidence=(row["rsi"] - self.get_param("rsi_overbought"))
                        / (100 - self.get_param("rsi_overbought")),
                        strategy_name=self.name,
                        market_state=self.detect_market_state(df.iloc[: i + 1]),
                        metadata={"rsi": row["rsi"], "bb_position": "upper"},
                    )
                )

        return signals

    def describe(self) -> dict:
        return {
            "name": self.name,
            "type": "mean_reversion",
            "description": "布林带+RSI均值回归策略，超卖区买入超买区卖出",
            "params": self.params,
            "suitable_markets": [MarketState.RANGE.value],
        }

    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))


class BreakoutStrategy(StrategyBase):
    def __init__(self, params: dict | None = None):
        default_params = {
            "channel_period": 20,
            "atr_period": 14,
            "atr_multiplier": 1.5,
            "rr_ratio": 3.0,
            "volume_factor": 1.3,
        }
        if params:
            default_params.update(params)
        super().__init__("breakout", default_params)

    def generate_signals(self, data: pd.DataFrame) -> list[Signal]:
        if len(data) < self.get_param("channel_period") + 10:
            return []

        df = data.copy()
        period = self.get_param("channel_period")
        atr_period = self.get_param("atr_period")
        atr_mult = self.get_param("atr_multiplier")
        rr_ratio = self.get_param("rr_ratio")

        df["highest"] = df["high"].rolling(window=period).max()
        df["lowest"] = df["low"].rolling(window=period).min()
        df["atr"] = TrendFollowingStrategy._calculate_atr(df, atr_period)
        df["vol_sma"] = df["volume"].rolling(window=period).mean()

        signals = []
        for i in range(period + 1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if pd.isna(row["highest"]) or pd.isna(row["atr"]):
                continue

            volume_confirm = (
                row["volume"] > row["vol_sma"] * self.get_param("volume_factor")
                if not pd.isna(row["vol_sma"])
                else True
            )

            if row["close"] > prev["highest"] and volume_confirm:
                stop_loss = row["close"] - row["atr"] * atr_mult
                _, take_profit = self.calculate_r_levels(row["close"], stop_loss, rr_ratio)
                risk = row["close"] - stop_loss
                reward = take_profit - row["close"]
                signals.append(
                    Signal(
                        symbol="",
                        signal_type=SignalType.BUY,
                        price=row["close"],
                        timestamp=df.index[i]
                        if isinstance(df.index[i], pd.Timestamp)
                        else pd.Timestamp.now(),
                        stop_loss=round(stop_loss, 4),
                        take_profit=round(take_profit, 4),
                        r_multiple=round(reward / risk, 2) if risk > 0 else 0,
                        confidence=0.8,
                        strategy_name=self.name,
                        market_state=self.detect_market_state(df.iloc[: i + 1]),
                        metadata={"channel_high": prev["highest"], "channel_low": prev["lowest"]},
                    )
                )

            elif row["close"] < prev["lowest"] and volume_confirm:
                stop_loss = row["close"] + row["atr"] * atr_mult
                _, take_profit = self.calculate_r_levels(row["close"], stop_loss, rr_ratio)
                risk = stop_loss - row["close"]
                reward = row["close"] - take_profit
                signals.append(
                    Signal(
                        symbol="",
                        signal_type=SignalType.SELL,
                        price=row["close"],
                        timestamp=df.index[i]
                        if isinstance(df.index[i], pd.Timestamp)
                        else pd.Timestamp.now(),
                        stop_loss=round(stop_loss, 4),
                        take_profit=round(take_profit, 4),
                        r_multiple=round(reward / risk, 2) if risk > 0 else 0,
                        confidence=0.8,
                        strategy_name=self.name,
                        market_state=self.detect_market_state(df.iloc[: i + 1]),
                        metadata={"channel_high": prev["highest"], "channel_low": prev["lowest"]},
                    )
                )

        return signals

    def describe(self) -> dict:
        return {
            "name": self.name,
            "type": "breakout",
            "description": "通道突破策略，突破N日最高价做多，突破N日最低价做空",
            "params": self.params,
            "suitable_markets": [MarketState.BULL.value, MarketState.BEAR.value],
        }


STRATEGY_REGISTRY: dict[str, type[StrategyBase]] = {
    "trend_following": TrendFollowingStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "sector_rotation": SectorRotationStrategy,
    "north_flow": NorthFlowStrategy,
}


def create_strategy(name: str, params: dict | None = None) -> StrategyBase:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name](params)


def list_strategies() -> list[dict]:
    return [cls().describe() for cls in STRATEGY_REGISTRY.values()]
