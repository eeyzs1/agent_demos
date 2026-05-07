import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SliceOrder:
    slice_index: int
    time_offset_minutes: float
    quantity: int
    limit_price: Optional[float] = None


@dataclass
class ExecutionSchedule:
    order_id: str
    symbol: str
    strategy: str
    total_quantity: int
    slices: list[SliceOrder]
    expected_avg_price: float
    expected_impact_bps: float
    arrival_price: float
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def num_slices(self) -> int:
        return len(self.slices)


class ExecutionScheduler:
    def __init__(self, impact_model=None, trading_minutes_per_day: int = 240):
        self._impact_model = impact_model
        self._trading_minutes_per_day = trading_minutes_per_day

    def generate_schedule(
        self,
        order_id: str = "",
        symbol: str = "",
        total_quantity: int = 0,
        arrival_price: float = 0.0,
        strategy: str = "twap",
        total_minutes: float = 30,
        num_slices: int = 10,
        daily_volume: float = 0.0,
        daily_volatility: float = 0.0,
        volume_profile: Optional[list[float]] = None,
        risk_aversion: float = 1e-6,
    ) -> ExecutionSchedule:
        if strategy == "twap":
            slices = self._generate_twap(total_quantity, total_minutes, num_slices)
            expected_impact_bps = 0.0
        elif strategy == "vwap":
            slices = self._generate_vwap(total_quantity, total_minutes, num_slices, volume_profile)
            expected_impact_bps = 0.0
        elif strategy == "implementation_shortfall":
            slices = self._generate_is(
                total_quantity, total_minutes, num_slices,
                arrival_price, daily_volume, daily_volatility, risk_aversion,
            )
            expected_impact_bps = self._estimate_is_impact(
                total_quantity, arrival_price, daily_volume, daily_volatility, total_minutes,
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}. Supported: twap, vwap, implementation_shortfall")

        expected_avg_price = arrival_price
        if slices:
            total_qty = sum(s.quantity for s in slices)
            if total_qty > 0:
                weights = [s.quantity / total_qty for s in slices]
                expected_avg_price = arrival_price * np.average(
                    [1.0] * len(slices), weights=weights
                )
            expected_avg_price = arrival_price

        schedule = ExecutionSchedule(
            order_id=order_id,
            symbol=symbol,
            strategy=strategy,
            total_quantity=total_quantity,
            slices=slices,
            expected_avg_price=expected_avg_price,
            expected_impact_bps=round(expected_impact_bps, 2),
            arrival_price=arrival_price,
        )

        logger.info(
            "Generated %s schedule: %d slices over %.0fmin, qty=%d",
            strategy, len(slices), total_minutes, total_quantity,
        )
        return schedule

    def _generate_twap(
        self, total_quantity: int, total_minutes: float, num_slices: int
    ) -> list[SliceOrder]:
        if num_slices <= 0 or total_quantity <= 0:
            return []

        base_qty = total_quantity // num_slices
        remainder = total_quantity - base_qty * num_slices
        interval = total_minutes / num_slices

        slices = []
        for i in range(num_slices):
            qty = base_qty + (1 if i < remainder else 0)
            qty = int(qty / 100) * 100
            if qty <= 0:
                qty = 100
            slices.append(SliceOrder(
                slice_index=i,
                time_offset_minutes=round(interval * (i + 1), 2),
                quantity=qty,
            ))

        return slices

    def _generate_vwap(
        self,
        total_quantity: int,
        total_minutes: float,
        num_slices: int,
        volume_profile: Optional[list[float]] = None,
    ) -> list[SliceOrder]:
        if num_slices <= 0 or total_quantity <= 0:
            return []

        if volume_profile is None or len(volume_profile) != num_slices:
            volume_profile = [1.0 / num_slices] * num_slices

        total_profile = sum(volume_profile)
        if total_profile <= 0:
            volume_profile = [1.0 / num_slices] * num_slices
            total_profile = 1.0

        norm_profile = [v / total_profile for v in volume_profile]
        interval = total_minutes / num_slices

        remaining = total_quantity
        slices = []
        for i in range(num_slices - 1):
            qty = int(total_quantity * norm_profile[i] / 100) * 100
            qty = min(qty, remaining)
            if qty <= 0:
                qty = 100
            slices.append(SliceOrder(
                slice_index=i,
                time_offset_minutes=round(interval * (i + 1), 2),
                quantity=qty,
            ))
            remaining -= qty

        last_qty = int(remaining / 100) * 100
        if last_qty <= 0:
            last_qty = 100
        slices.append(SliceOrder(
            slice_index=num_slices - 1,
            time_offset_minutes=total_minutes,
            quantity=last_qty,
        ))

        return slices

    def _generate_is(
        self,
        total_quantity: int,
        total_minutes: float,
        num_slices: int,
        arrival_price: float,
        daily_volume: float,
        daily_volatility: float,
        risk_aversion: float,
    ) -> list[SliceOrder]:
        T = total_minutes / self._trading_minutes_per_day
        if daily_volume <= 0 or daily_volatility <= 0 or T <= 0:
            return self._generate_twap(total_quantity, total_minutes, num_slices)

        sigma = daily_volatility
        Q = total_quantity
        V = daily_volume

        eta_val = 0.15
        if self._impact_model and hasattr(self._impact_model, 'eta'):
            eta_val = self._impact_model.eta

        kappa = risk_aversion * sigma**2 / (eta_val * sigma * Q / (V * T))
        if kappa <= 0:
            kappa = 0.01

        interval = total_minutes / num_slices
        slices = []
        for i in range(num_slices):
            t_i = (i + 1) * interval / total_minutes
            remaining_frac = np.sinh(kappa * (1 - t_i)) / np.sinh(kappa) if np.sinh(kappa) > 1e-10 else (1 - t_i)
            qty = int(total_quantity * (1 - remaining_frac) / num_slices)
            qty = int(qty / 100) * 100
            if qty <= 0:
                qty = 100
            slices.append(SliceOrder(
                slice_index=i,
                time_offset_minutes=round(interval * (i + 1), 2),
                quantity=qty,
            ))

        total_sliced = sum(s.quantity for s in slices)
        if total_sliced < total_quantity:
            diff = total_quantity - total_sliced
            for s in slices:
                add = min(diff, 100)
                s.quantity += add
                diff -= add
                if diff <= 0:
                    break

        return slices

    def _estimate_is_impact(
        self,
        total_quantity: int,
        arrival_price: float,
        daily_volume: float,
        daily_volatility: float,
        total_minutes: float,
    ) -> float:
        if self._impact_model is None or daily_volume <= 0:
            return 0.0

        impact = self._impact_model.estimate_impact(
            symbol="",
            order_quantity=total_quantity,
            order_side="BUY",
            arrival_price=arrival_price,
            daily_volume=daily_volume,
            daily_volatility=daily_volatility,
            execution_horizon_minutes=total_minutes,
        )
        return impact.total_impact_bps

    def execute_schedule(
        self,
        broker,
        schedule: ExecutionSchedule,
        on_fill_callback: Optional[Callable] = None,
        paused: bool = False,
    ) -> list:
        results = []
        if paused:
            logger.info("Execution paused for schedule %s", schedule.order_id)
            return results

        for slc in schedule.slices:
            from trading_system.execution.broker import Order, OrderSide, OrderType

            order = Order(
                order_id=f"{schedule.order_id}-S{slc.slice_index}",
                symbol=schedule.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=slc.quantity,
                price=schedule.arrival_price,
                metadata={"slice_index": slc.slice_index, "parent_order_id": schedule.order_id},
            )
            filled = broker.submit_order(order)
            results.append(filled)

            if on_fill_callback:
                on_fill_callback(filled)

        logger.info(
            "Executed %d slices for schedule %s",
            len(results), schedule.order_id,
        )
        return results
