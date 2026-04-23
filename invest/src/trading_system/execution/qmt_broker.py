import logging
from datetime import datetime
from typing import Optional

from trading_system.execution.broker import (
    BrokerInterface,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)

logger = logging.getLogger(__name__)


class QmtBroker(BrokerInterface):
    def __init__(
        self,
        qmt_path: str = "",
        account_id: str = "",
        password: str = "",
        trade_mode: int = 0,
        reconnect_attempts: int = 3,
        heartbeat_interval: int = 30,
    ):
        self._qmt_path = qmt_path
        self._account_id = account_id
        self._password = password
        self._trade_mode = trade_mode
        self._reconnect_attempts = reconnect_attempts
        self._heartbeat_interval = heartbeat_interval
        self._connected = False
        self._xt_trader = None
        self._xt_account = None
        self._last_heartbeat = None

    def connect(self) -> bool:
        for attempt in range(self._reconnect_attempts):
            try:
                from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
                from xtquant.xttype import StockAccount

                session_id = int(datetime.now().timestamp() * 1000)
                self._xt_trader = XtQuantTrader(self._qmt_path, session_id)

                self._xt_account = StockAccount(self._account_id)
                self._connected = self._xt_trader.connect()

                if self._connected:
                    self._xt_trader.subscribe_account(self._xt_account)
                    self._last_heartbeat = datetime.now()
                    logger.info("QMT connected successfully (account: %s)", self._account_id)
                    return True
                else:
                    logger.warning("QMT connect attempt %d failed", attempt + 1)

            except ImportError:
                logger.error("xtquant not installed. Install QMT SDK first.")
                return False
            except Exception as e:
                logger.error("QMT connect attempt %d error: %s", attempt + 1, e)

        logger.error("QMT connection failed after %d attempts", self._reconnect_attempts)
        return False

    def disconnect(self) -> None:
        if self._xt_trader:
            try:
                self._xt_trader.stop()
            except Exception as e:
                logger.error("QMT disconnect error: %s", e)
            finally:
                self._connected = False
                self._xt_trader = None

    def check_heartbeat(self) -> bool:
        if not self._connected or not self._xt_trader:
            return False

        try:
            asset = self._xt_trader.query_stock_asset(self._xt_account)
            if asset is not None:
                self._last_heartbeat = datetime.now()
                return True
        except Exception as e:
            logger.error("QMT heartbeat failed: %s", e)

        return False

    def reconnect(self) -> bool:
        self.disconnect()
        return self.connect()

    def submit_order(self, order: Order) -> Order:
        if not self._connected:
            order.status = OrderStatus.REJECTED
            order.updated_at = datetime.now()
            return order

        try:
            from xtquant.xttype import StockOrder

            xt_order = StockOrder()
            xt_order.account = self._xt_account
            xt_order.stock_code = order.symbol
            xt_order.price = order.price or 0.0
            xt_order.volume = int(order.quantity)
            xt_order.strategy_name = order.strategy_name

            if order.side == OrderSide.BUY:
                xt_order.order_side = 23
            else:
                xt_order.order_side = 24

            if order.order_type == OrderType.MARKET:
                xt_order.price_type = 5
            else:
                xt_order.price_type = 11

            order_id = self._xt_trader.order_stock(self._xt_account, xt_order)

            if order_id > 0:
                order.order_id = f"QMT-{order_id}"
                order.status = OrderStatus.SUBMITTED
                logger.info("QMT order submitted: %s", order.order_id)
            else:
                order.status = OrderStatus.REJECTED
                logger.warning("QMT order rejected for %s", order.symbol)

        except Exception as e:
            order.status = OrderStatus.REJECTED
            logger.error("QMT submit_order error: %s", e)

        order.updated_at = datetime.now()
        return order

    def cancel_order(self, order_id: str) -> bool:
        if not self._connected:
            return False

        try:
            qmt_id = int(order_id.replace("QMT-", ""))
            result = self._xt_trader.cancel_order_stock(self._xt_account, qmt_id)
            return result == 0
        except Exception as e:
            logger.error("QMT cancel_order error: %s", e)
            return False

    def get_positions(self) -> list[dict]:
        if not self._connected:
            return []

        try:
            positions = self._xt_trader.query_stock_positions(self._xt_account)
            result = []
            for pos in positions:
                result.append({
                    "symbol": pos.stock_code,
                    "quantity": pos.volume,
                    "available": pos.can_use_volume,
                    "cost_price": pos.open_price,
                    "market_value": pos.market_value,
                    "profit": pos.market_value - pos.open_price * pos.volume,
                })
            return result
        except Exception as e:
            logger.error("QMT get_positions error: %s", e)
            return []

    def get_order(self, order_id: str) -> Optional[Order]:
        if not self._connected:
            return None
        try:
            qmt_id = int(order_id.replace("QMT-", ""))
            orders = self._xt_trader.query_stock_orders(self._xt_account)
            for o in orders:
                if o.order_id == qmt_id:
                    return Order(
                        order_id=order_id,
                        symbol=o.stock_code,
                        side=OrderSide.BUY if o.order_side == 23 else OrderSide.SELL,
                        order_type=OrderType.MARKET if o.price_type == 5 else OrderType.LIMIT,
                        quantity=o.volume,
                        price=o.price,
                        filled_quantity=o.traded_volume,
                        filled_price=o.traded_price if o.traded_volume > 0 else None,
                        status=OrderStatus.FILLED if o.traded_volume == o.volume else OrderStatus.SUBMITTED,
                    )
        except Exception as e:
            logger.error("QMT get_order error: %s", e)
        return None

    def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        if not self._connected:
            return []
        try:
            orders = self._xt_trader.query_stock_orders(self._xt_account)
            result = []
            for o in orders:
                if o.traded_volume < o.volume:
                    if symbol and o.stock_code != symbol:
                        continue
                    result.append(Order(
                        order_id=f"QMT-{o.order_id}",
                        symbol=o.stock_code,
                        side=OrderSide.BUY if o.order_side == 23 else OrderSide.SELL,
                        order_type=OrderType.MARKET if o.price_type == 5 else OrderType.LIMIT,
                        quantity=o.volume,
                        price=o.price,
                        filled_quantity=o.traded_volume,
                        status=OrderStatus.SUBMITTED,
                    ))
            return result
        except Exception as e:
            logger.error("QMT get_open_orders error: %s", e)
            return []

    def get_account_balance(self) -> dict:
        return self.get_account()

    def get_account(self) -> dict:
        if not self._connected:
            return {}

        try:
            asset = self._xt_trader.query_stock_asset(self._xt_account)
            if asset:
                return {
                    "total_asset": asset.total_asset,
                    "cash": asset.cash,
                    "market_value": asset.market_value,
                    "frozen_cash": asset.frozen_cash,
                    "available_cash": asset.cash - asset.frozen_cash,
                }
            return {}
        except Exception as e:
            logger.error("QMT get_account error: %s", e)
            return {}

    @property
    def is_connected(self) -> bool:
        return self._connected
