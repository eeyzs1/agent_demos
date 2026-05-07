import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TCAOrderRecord:
    order_id: str
    symbol: str
    side: str
    quantity: float
    arrival_price: float
    execution_avg_price: float
    vwap: float
    is_bps: float
    delay_bps: float
    impact_bps: float
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "arrival_price": self.arrival_price,
            "execution_avg_price": self.execution_avg_price,
            "vwap": self.vwap,
            "is_bps": self.is_bps,
            "delay_bps": self.delay_bps,
            "impact_bps": self.impact_bps,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TCAOrderRecord":
        return cls(
            order_id=d["order_id"],
            symbol=d["symbol"],
            side=d["side"],
            quantity=d["quantity"],
            arrival_price=d["arrival_price"],
            execution_avg_price=d["execution_avg_price"],
            vwap=d["vwap"],
            is_bps=d["is_bps"],
            delay_bps=d["delay_bps"],
            impact_bps=d["impact_bps"],
            created_at=d["created_at"],
        )


@dataclass
class WeeklyTCAReport:
    period_start: str
    period_end: str
    records: list[TCAOrderRecord]
    by_symbol: dict = field(default_factory=dict)
    by_strategy: dict = field(default_factory=dict)
    by_order_side: dict = field(default_factory=dict)

    @property
    def avg_execution_cost_bps(self) -> float:
        if not self.records:
            return 0.0
        return np.mean([r.is_bps for r in self.records])

    def cost_percentiles(self) -> dict:
        if not self.records:
            return {"P25": 0.0, "P50": 0.0, "P75": 0.0, "P95": 0.0}
        costs = [r.is_bps for r in self.records]
        return {
            "P25": round(float(np.percentile(costs, 25)), 2),
            "P50": round(float(np.percentile(costs, 50)), 2),
            "P75": round(float(np.percentile(costs, 75)), 2),
            "P95": round(float(np.percentile(costs, 95)), 2),
        }


class TransactionCostAnalyzer:
    def __init__(self, db_path: str = "sqlite:///./data/tca.db"):
        self._db_path = db_path
        self._records: list[TCAOrderRecord] = []

    def analyze_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        arrival_price: float,
        execution_prices: list[float],
        vwap: float,
        decision_price: Optional[float] = None,
    ) -> TCAOrderRecord:
        if not execution_prices:
            return TCAOrderRecord(
                order_id=order_id, symbol=symbol, side=side,
                quantity=quantity, arrival_price=arrival_price,
                execution_avg_price=arrival_price, vwap=vwap,
                is_bps=0.0, delay_bps=0.0, impact_bps=0.0,
            )

        exec_avg = float(np.mean(execution_prices))

        if arrival_price <= 0:
            is_bps = 0.0
            delay_bps = 0.0
            impact_bps = 0.0
        else:
            side_mult = 1 if side.upper() == "BUY" else -1
            is_bps = side_mult * (exec_avg - arrival_price) / arrival_price * 10000

            if len(execution_prices) >= 2:
                first_price = execution_prices[0]
                delay_bps = side_mult * (first_price - arrival_price) / arrival_price * 10000
                last_price = execution_prices[-1]
                impact_bps = side_mult * (last_price - first_price) / first_price * 10000
            else:
                delay_bps = is_bps
                impact_bps = 0.0

        if vwap > 0:
            vwap_slippage = (exec_avg / vwap - 1) * 10000
        else:
            vwap_slippage = 0.0

        record = TCAOrderRecord(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            arrival_price=arrival_price,
            execution_avg_price=round(exec_avg, 4),
            vwap=round(vwap, 4),
            is_bps=round(is_bps, 2),
            delay_bps=round(delay_bps, 2),
            impact_bps=round(impact_bps, 2),
        )

        self._records.append(record)
        logger.info(
            "TCA for %s: IS=%.2fbps delay=%.2fbps impact=%.2fbps vwap_slip=%.2fbps",
            order_id, is_bps, delay_bps, impact_bps, vwap_slippage,
        )
        return record

    def get_order_tca(self, order_id: str) -> Optional[TCAOrderRecord]:
        for r in self._records:
            if r.order_id == order_id:
                return r
        return None

    def generate_weekly_report(
        self,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> WeeklyTCAReport:
        if period_start is None:
            period_start = (datetime.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        if period_end is None:
            period_end = datetime.now().strftime("%Y-%m-%d")

        week_records = [
            r for r in self._records
            if period_start <= r.created_at[:10] <= period_end
        ]

        by_symbol: dict[str, list] = {}
        for r in week_records:
            by_symbol.setdefault(r.symbol, []).append(r)

        by_side: dict[str, list] = {}
        for r in week_records:
            by_side.setdefault(r.side, []).append(r)

        report = WeeklyTCAReport(
            period_start=period_start,
            period_end=period_end,
            records=week_records,
            by_symbol={
                sym: {
                    "count": len(recs),
                    "avg_cost_bps": round(np.mean([r.is_bps for r in recs]), 2),
                    "total_quantity": sum(r.quantity for r in recs),
                }
                for sym, recs in by_symbol.items()
            },
            by_order_side={
                side: {
                    "count": len(recs),
                    "avg_cost_bps": round(np.mean([r.is_bps for r in recs]), 2),
                }
                for side, recs in by_side.items()
            },
        )

        logger.info(
            "Weekly TCA Report: %d orders, avg cost %.2fbps",
            len(week_records), report.avg_execution_cost_bps,
        )
        return report

    @property
    def record_count(self) -> int:
        return len(self._records)
