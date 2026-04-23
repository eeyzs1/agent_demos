import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    strategy_name: str = ""
    commission: float = 0.0
    slippage: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status in (
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
        )

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED


class BrokerInterface(ABC):
    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        pass

    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        pass

    @abstractmethod
    def get_account_balance(self) -> dict:
        pass

    @abstractmethod
    def get_positions(self) -> dict:
        pass


class PaperBroker(BrokerInterface):
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.0003,
        slippage_pct: float = 0.001,
        enable_limit_check: bool = False,
        use_ashare_cost: bool = False,
    ):
        self._capital = initial_capital
        self._commission_rate = commission_rate
        self._slippage_pct = slippage_pct
        self._enable_limit_check = enable_limit_check
        self._use_ashare_cost = use_ashare_cost
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, dict] = {}
        self._order_counter = 0

    def submit_order(self, order: Order) -> Order:
        self._order_counter += 1
        if not order.order_id:
            order.order_id = f"PAPER-{self._order_counter:06d}"

        if order.order_type == OrderType.MARKET:
            fill_price = order.price or 0.0
            if fill_price <= 0:
                order.status = OrderStatus.REJECTED
                order.updated_at = datetime.now()
                self._orders[order.order_id] = order
                return order

            if self._enable_limit_check:
                prev_close = order.metadata.get("prev_close") if hasattr(order, "metadata") else None
                if prev_close:
                    from trading_system.ashare.calculator import clamp_price, detect_board_type
                    board_type = detect_board_type(order.symbol)
                    fill_price = clamp_price(fill_price, prev_close, board_type)

            if order.side == OrderSide.BUY:
                fill_price *= 1 + self._slippage_pct
            else:
                fill_price *= 1 - self._slippage_pct

            if self._use_ashare_cost:
                from trading_system.ashare.cost_model import AShareCostCalculator
                cost_calc = AShareCostCalculator()
                if order.side == OrderSide.BUY:
                    cost = cost_calc.calc_buy_cost(fill_price, order.quantity)
                else:
                    cost = cost_calc.calc_sell_cost(fill_price, order.quantity)
                commission = cost.total_cost
            else:
                commission = fill_price * order.quantity * self._commission_rate
            order.filled_price = fill_price
            order.filled_quantity = order.quantity
            order.commission = commission
            order.status = OrderStatus.FILLED
            order.updated_at = datetime.now()

            self._update_position(order)
        else:
            order.status = OrderStatus.SUBMITTED
            order.updated_at = datetime.now()

        self._orders[order.order_id] = order
        logger.info(
            "Order %s: %s %s %s@%s → %s",
            order.order_id,
            order.side.value,
            order.symbol,
            order.quantity,
            order.filled_price,
            order.status.value,
        )
        return order

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order and order.is_active:
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            return True
        return False

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        orders = [o for o in self._orders.values() if o.is_active]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_account_balance(self) -> dict:
        position_value = sum(p["quantity"] * p["avg_price"] for p in self._positions.values())
        return {
            "cash": self._capital,
            "position_value": position_value,
            "total_equity": self._capital + position_value,
        }

    def get_positions(self) -> dict:
        return dict(self._positions)

    def _update_position(self, order: Order) -> None:
        symbol = order.symbol
        if order.side == OrderSide.BUY:
            cost = order.filled_price * order.quantity + order.commission
            self._capital -= cost
            if symbol in self._positions:
                pos = self._positions[symbol]
                total_qty = pos["quantity"] + order.quantity
                avg_price = (
                    pos["avg_price"] * pos["quantity"] + order.filled_price * order.quantity
                ) / total_qty
                self._positions[symbol] = {"quantity": total_qty, "avg_price": avg_price}
            else:
                self._positions[symbol] = {
                    "quantity": order.quantity,
                    "avg_price": order.filled_price,
                }
        elif order.side == OrderSide.SELL:
            if symbol in self._positions:
                pos = self._positions[symbol]
                sell_qty = min(order.quantity, pos["quantity"])
                proceeds = order.filled_price * sell_qty - order.commission
                self._capital += proceeds
                remaining = pos["quantity"] - sell_qty
                if remaining <= 0:
                    del self._positions[symbol]
                else:
                    self._positions[symbol] = {"quantity": remaining, "avg_price": pos["avg_price"]}
