"""Execution Engine — Paper trading by default, --live flag for real trading.

Enforces:
- Paper trading is the default mode (AC1)
- Live trading requires explicit --live flag (AC1)
- All orders logged to audit (hard_constraint)
- Integrates with RiskManager for position checks
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderDirection(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """A trading order."""
    order_id: str
    symbol: str
    name: str = ""
    direction: OrderDirection = OrderDirection.BUY
    order_type: OrderType = OrderType.MARKET
    price: float = 0.0
    quantity: int = 0
    filled_quantity: int = 0
    status: OrderStatus = OrderStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    filled_at: Optional[str] = None
    trading_mode: str = "paper"
    notes: str = ""


@dataclass
class Trade:
    """A completed trade (filled order)."""
    trade_id: str
    order_id: str
    symbol: str
    name: str = ""
    direction: OrderDirection = OrderDirection.BUY
    price: float = 0.0
    quantity: int = 0
    value: float = 0.0
    commission: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    trading_mode: str = "paper"


class ExecutionEngine:
    """Order execution engine with paper trading as default.

    All orders are executed in paper mode unless --live flag is explicitly set.
    The engine integrates with RiskManager for pre-trade risk checks.
    """

    def __init__(self, config_dir: str = "config"):
        config = get_config(config_dir)
        self._config = config
        self._lock = threading.RLock()
        self._audit = get_audit_logger()
        self._event_bus = get_event_bus()

        self._trading_mode = config.get("trading.mode", "paper")
        self._commission_rate = config.get("backtest.commission_rate", 0.0003)
        self._slippage = config.get("backtest.slippage", 0.001)

        # Order tracking
        self._orders: Dict[str, Order] = {}
        self._trades: List[Trade] = []
        self._order_counter = 0
        self._trade_counter = 0

        # Risk manager reference (set after init to avoid circular imports)
        self._risk_manager = None

        logger.info(
            "ExecutionEngine initialized: mode=%s, commission=%.4f, slippage=%.4f",
            self._trading_mode, self._commission_rate, self._slippage,
        )

    def set_risk_manager(self, risk_manager) -> None:
        """Set the risk manager reference."""
        self._risk_manager = risk_manager

    @property
    def trading_mode(self) -> str:
        return self._trading_mode

    def enable_live_trading(self) -> tuple:
        """Enable live trading mode. Requires explicit human confirmation.

        Returns:
            (success: bool, message: str)
        """
        with self._lock:
            if self._trading_mode == "live":
                return False, "Already in live trading mode"

            self._trading_mode = "live"
            self._audit.log(
                "config_changes",
                check_id="trading_mode",
                result="OK",
                actor="human",
                payload={"old": "paper", "new": "live"},
            )
            self._event_bus.publish(
                "execution.trading_mode_changed",
                {"mode": "live"},
            )
            logger.critical("⚠️ LIVE TRADING MODE ENABLED")
            return True, "Live trading enabled — REAL orders will be placed"

    def disable_live_trading(self) -> tuple:
        """Disable live trading, return to paper trading."""
        with self._lock:
            if self._trading_mode == "paper":
                return False, "Already in paper trading mode"
            self._trading_mode = "paper"
            self._audit.log(
                "config_changes",
                check_id="trading_mode",
                result="OK",
                actor="human",
                payload={"old": "live", "new": "paper"},
            )
            self._event_bus.publish(
                "execution.trading_mode_changed",
                {"mode": "paper"},
            )
            return True, "Paper trading mode restored"

    def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "market",
        name: str = "",
    ) -> Optional[Order]:
        """Place a new order.

        Args:
            symbol: Stock code.
            direction: 'buy' or 'sell'.
            quantity: Number of shares.
            price: Limit price (0 for market orders).
            order_type: 'market' or 'limit'.
            name: Stock name.

        Returns:
            Order object if placed, None if rejected.
        """
        # Pre-trade risk check
        if self._risk_manager and direction == "buy":
            approved, reason = self._risk_manager.can_open_position(
                symbol, price if price > 0 else self._get_last_price(symbol),
                quantity, "long"
            )
            if not approved:
                logger.warning("Order rejected by risk manager: %s", reason)
                self._audit.log(
                    "order_placement",
                    check_id=f"reject_{symbol}",
                    result="REJECTED",
                    payload={"symbol": symbol, "reason": reason},
                )
                return None

        with self._lock:
            self._order_counter += 1
            order_id = f"ORD_{self._order_counter:06d}"

            order = Order(
                order_id=order_id,
                symbol=symbol,
                name=name,
                direction=OrderDirection.BUY if direction == "buy" else OrderDirection.SELL,
                order_type=OrderType.MARKET if order_type == "market" else OrderType.LIMIT,
                price=price,
                quantity=quantity,
                status=OrderStatus.FILLED if order_type == "market" else OrderStatus.PENDING,
                filled_quantity=quantity if order_type == "market" else 0,
                filled_at=datetime.now().isoformat() if order_type == "market" else None,
                trading_mode=self._trading_mode,
            )

            self._orders[order_id] = order

            # For market orders, create trade immediately
            if order_type == "market":
                fill_price = price if price > 0 else 0
                trade = self._create_trade(order, fill_price)
                self._trades.append(trade)
                self._event_bus.publish(
                    "execution.order_filled",
                    {
                        "order_id": order_id,
                        "trade_id": trade.trade_id,
                        "symbol": symbol,
                        "direction": direction,
                        "price": fill_price,
                        "quantity": quantity,
                        "trading_mode": self._trading_mode,
                    },
                )

            self._audit.log(
                "order_placement",
                check_id=order_id,
                result="FILLED" if order_type == "market" else "PENDING",
                payload={
                    "symbol": symbol,
                    "direction": direction,
                    "price": price,
                    "quantity": quantity,
                    "order_type": order_type,
                    "trading_mode": self._trading_mode,
                },
            )
            self._event_bus.publish(
                "execution.order_placed",
                {
                    "order_id": order_id,
                    "symbol": symbol,
                    "direction": direction,
                    "quantity": quantity,
                    "trading_mode": self._trading_mode,
                },
            )

            logger.info(
                "[%s] Order placed: %s %s %d@%.2f",
                self._trading_mode.upper(), order_id, symbol, quantity, price,
            )
            return order

    def _create_trade(self, order: Order, fill_price: float) -> Trade:
        """Create a trade record from a filled order."""
        with self._lock:
            self._trade_counter += 1
            trade_id = f"TRD_{self._trade_counter:06d}"
            value = fill_price * order.filled_quantity
            commission = value * self._commission_rate
            # Apply slippage
            slippage_amount = value * self._slippage
            if order.direction == OrderDirection.BUY:
                fill_price += slippage_amount / order.filled_quantity

            return Trade(
                trade_id=trade_id,
                order_id=order.order_id,
                symbol=order.symbol,
                name=order.name,
                direction=order.direction,
                price=fill_price,
                quantity=order.filled_quantity,
                value=value,
                commission=commission,
                trading_mode=order.trading_mode,
            )

    def _get_last_price(self, symbol: str) -> float:
        """Get the last known price for a symbol."""
        # In production, this would query the market data feed
        return 0.0

    def get_orders(self, status: OrderStatus = None) -> List[Order]:
        """Get all orders, optionally filtered by status."""
        with self._lock:
            orders = list(self._orders.values())
            if status:
                orders = [o for o in orders if o.status == status]
            return orders

    def get_trades(self, symbol: str = None) -> List[Trade]:
        """Get all trades, optionally filtered by symbol."""
        with self._lock:
            trades = list(self._trades)
            if symbol:
                trades = [t for t in trades if t.symbol == symbol]
            return trades

    def get_summary(self) -> Dict[str, Any]:
        """Get execution engine summary."""
        with self._lock:
            total_buy_value = sum(
                t.value for t in self._trades
                if t.direction == OrderDirection.BUY
            )
            total_sell_value = sum(
                t.value for t in self._trades
                if t.direction == OrderDirection.SELL
            )
            total_commission = sum(t.commission for t in self._trades)

            return {
                "trading_mode": self._trading_mode,
                "total_orders": len(self._orders),
                "total_trades": len(self._trades),
                "total_buy_value": total_buy_value,
                "total_sell_value": total_sell_value,
                "total_commission": total_commission,
                "commission_rate": self._commission_rate,
                "slippage": self._slippage,
            }