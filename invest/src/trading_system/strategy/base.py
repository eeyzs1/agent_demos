from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"

    @classmethod
    def from_signal(cls, signal_type: SignalType) -> "PositionSide":
        return cls.LONG if signal_type == SignalType.BUY else cls.SHORT

    @classmethod
    def from_order_side(cls, order_side) -> "PositionSide":
        from trading_system.execution.broker import OrderSide

        return cls.LONG if order_side == OrderSide.BUY else cls.SHORT


class MarketState(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"


@dataclass
class Signal:
    symbol: str
    signal_type: SignalType
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    r_multiple: Optional[float] = None
    confidence: float = 1.0
    strategy_name: str = ""
    market_state: MarketState = MarketState.UNKNOWN
    metadata: dict = field(default_factory=dict)

    @property
    def risk_amount(self) -> float:
        if self.stop_loss and self.signal_type == SignalType.BUY:
            return self.price - self.stop_loss
        if self.stop_loss and self.signal_type == SignalType.SELL:
            return self.stop_loss - self.price
        return 0.0

    @property
    def reward_amount(self) -> float:
        if self.take_profit and self.signal_type == SignalType.BUY:
            return self.take_profit - self.price
        if self.take_profit and self.signal_type == SignalType.SELL:
            return self.price - self.take_profit
        return 0.0

    @property
    def risk_reward_ratio(self) -> float:
        if self.risk_amount > 0:
            return self.reward_amount / self.risk_amount
        return 0.0


class StrategyBase(ABC):
    def __init__(self, name: str, params: Optional[dict] = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> list[Signal]:
        pass

    @abstractmethod
    def describe(self) -> dict:
        pass

    def set_param(self, key: str, value) -> None:
        self.params[key] = value

    def get_param(self, key: str, default=None):
        return self.params.get(key, default)

    def calculate_r_levels(
        self,
        entry_price: float,
        stop_loss: float,
        rr_ratio: float = 3.0,
    ) -> tuple[float, float]:
        risk = abs(entry_price - stop_loss)
        if entry_price > stop_loss:
            take_profit = entry_price + risk * rr_ratio
        else:
            take_profit = entry_price - risk * rr_ratio
        return stop_loss, take_profit

    @staticmethod
    def detect_market_state(data: pd.DataFrame, window: int = 50) -> MarketState:
        from trading_system.analysis.market import MarketAnalyzer

        return MarketAnalyzer.detect_state(data, window)
