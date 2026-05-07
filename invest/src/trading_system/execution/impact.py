import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ImpactEstimate:
    symbol: str
    order_quantity: int
    order_side: str
    temporary_impact_bps: float
    permanent_impact_bps: float
    total_impact_bps: float
    expected_slippage_price: float
    arrival_price: float
    daily_volume: float
    daily_volatility: float
    execution_horizon_minutes: int


class MarketImpactModel:
    def __init__(
        self,
        eta: float = 0.15,
        beta: float = 0.6,
        gamma: float = 0.05,
        trading_minutes_per_day: int = 240,
    ):
        self._eta = eta
        self._beta = beta
        self._gamma = gamma
        self._trading_minutes_per_day = trading_minutes_per_day

    def estimate_impact(
        self,
        symbol: str,
        order_quantity: int,
        order_side: str,
        arrival_price: float,
        daily_volume: float,
        daily_volatility: float,
        execution_horizon_minutes: float = 30,
    ) -> ImpactEstimate:
        if daily_volume <= 0:
            logger.warning("Daily volume is 0 for %s, returning zero impact", symbol)
            return ImpactEstimate(
                symbol=symbol,
                order_quantity=order_quantity,
                order_side=order_side,
                temporary_impact_bps=0.0,
                permanent_impact_bps=0.0,
                total_impact_bps=0.0,
                expected_slippage_price=arrival_price,
                arrival_price=arrival_price,
                daily_volume=daily_volume,
                daily_volatility=daily_volatility,
                execution_horizon_minutes=int(execution_horizon_minutes),
            )

        T = execution_horizon_minutes / self._trading_minutes_per_day
        participation_rate = order_quantity / (daily_volume * T) if T > 0 else order_quantity / daily_volume

        sigma = daily_volatility

        temporary_impact_pct = self._eta * sigma * (participation_rate ** self._beta)
        permanent_impact_pct = self._gamma * sigma * participation_rate

        temporary_impact_bps = temporary_impact_pct * 10000
        permanent_impact_bps = permanent_impact_pct * 10000
        total_impact_pct = temporary_impact_pct + permanent_impact_pct
        total_impact_bps = total_impact_pct * 10000

        if order_side.upper() == "BUY":
            expected_slippage_price = arrival_price * (1 + total_impact_pct)
        else:
            expected_slippage_price = arrival_price * (1 - total_impact_pct)

        logger.info(
            "Impact estimate for %s: qty=%d side=%s temp=%.2fbps perm=%.2fbps total=%.2fbps",
            symbol, order_quantity, order_side,
            temporary_impact_bps, permanent_impact_bps, total_impact_bps,
        )

        return ImpactEstimate(
            symbol=symbol,
            order_quantity=order_quantity,
            order_side=order_side,
            temporary_impact_bps=round(temporary_impact_bps, 2),
            permanent_impact_bps=round(permanent_impact_bps, 2),
            total_impact_bps=round(total_impact_bps, 2),
            expected_slippage_price=round(expected_slippage_price, 4),
            arrival_price=arrival_price,
            daily_volume=daily_volume,
            daily_volatility=round(daily_volatility, 4),
            execution_horizon_minutes=int(execution_horizon_minutes),
        )

    def apply_impact(
        self,
        price: float,
        order_quantity: int,
        order_side: str,
        daily_volume: float,
        daily_volatility: float,
        execution_horizon_minutes: float = 30,
    ) -> float:
        order_side_upper = order_side.upper()
        impact = self.estimate_impact(
            symbol="",
            order_quantity=order_quantity,
            order_side=order_side_upper,
            arrival_price=price,
            daily_volume=daily_volume,
            daily_volatility=daily_volatility,
            execution_horizon_minutes=execution_horizon_minutes,
        )
        return impact.expected_slippage_price

    @property
    def eta(self) -> float:
        return self._eta

    @property
    def beta(self) -> float:
        return self._beta

    @property
    def gamma(self) -> float:
        return self._gamma
