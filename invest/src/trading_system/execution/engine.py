import logging
import time
from datetime import datetime
from typing import Optional

from trading_system.ashare.trading_session import TradingSession
from trading_system.core.audit import AuditLogger
from trading_system.core.config import AppConfig
from trading_system.core.container import ServiceContainer, create_container
from trading_system.core.events import Event, EventBus, EventType
from trading_system.execution.broker import (
    BrokerInterface,
    Order,
    OrderSide,
    OrderType,
)
from trading_system.notification.manager import NotificationManager
from trading_system.risk.manager import RiskManager
from trading_system.strategy.base import PositionSide, Signal, SignalType

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(
        self,
        config: AppConfig,
        event_bus: Optional[EventBus] = None,
        audit_logger: Optional[AuditLogger] = None,
        container: Optional[ServiceContainer] = None,
    ):
        self._config = config
        self._event_bus = event_bus or EventBus()
        self._audit = audit_logger or AuditLogger()

        if container is not None:
            self._container = container
        else:
            self._container = create_container(config)

        self._data_store = self._container.get("data_store")
        self._risk_manager = self._container.get("risk_manager")

        if self._risk_manager is None:
            from trading_system.risk.manager import RiskManager
            self._risk_manager = RiskManager(config.risk, config.trading.initial_capital)

        if config.trading.mode == "paper":
            self._broker: BrokerInterface = self._container.get("broker")
        elif config.trading.mode == "qmt":
            from trading_system.execution.qmt_broker import QmtBroker
            self._broker = QmtBroker(
                qmt_path=config.trading.qmt_path,
                account_id=config.trading.qmt_account,
                password=config.trading.qmt_password,
            )
            connect_result = self._broker.connect()
            if not connect_result:
                logger.warning("QMT connection failed, falling back to paper mode")
                self._broker = self._container.get("broker")
        else:
            self._audit.log_action(
                "live_mode_unavailable",
                "system",
                {"message": "Live trading mode is not yet implemented, falling back to paper mode"},
            )
            logger.warning(
                "Live trading mode is NOT implemented. Falling back to paper mode. "
                "Do NOT rely on this for real trading."
            )
            self._broker = self._container.get("broker")

        self._notification = self._container.get("notification_manager")

        self._running = False
        self._strategies: dict = {}
        self._trading_session = TradingSession()

    @property
    def risk_manager(self) -> RiskManager:
        return self._risk_manager

    @property
    def broker(self) -> BrokerInterface:
        return self._broker

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def notification(self) -> NotificationManager:
        return self._notification

    def register_strategy(self, name: str, strategy) -> None:
        self._strategies[name] = strategy
        self._audit.log_action("register_strategy", "system", {"strategy": name})

    def process_signal(self, signal: Signal) -> Optional[Order]:
        self._risk_manager.update_price_history(signal.symbol, signal.price)

        if signal.signal_type == SignalType.SELL:
            return self._handle_sell_signal(signal)

        valid, reason = self._risk_manager.validate_signal(signal)
        if not valid:
            logger.warning("Signal rejected: %s - %s", signal.symbol, reason)
            self._audit.log_action(
                "signal_rejected",
                signal.strategy_name,
                {"symbol": signal.symbol, "reason": reason},
            )
            self._event_bus.publish_sync(
                Event(
                    type=EventType.ORDER_REJECTED,
                    data={"symbol": signal.symbol, "reason": reason},
                    source=signal.strategy_name,
                )
            )
            return None

        quantity = self._risk_manager.calculate_position_size(signal)
        if quantity <= 0:
            logger.warning("Position size is 0 for %s", signal.symbol)
            return None

        order = Order(
            order_id="",
            symbol=signal.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=signal.price,
            strategy_name=signal.strategy_name,
        )

        filled_order = self._broker.submit_order(order)

        if filled_order.is_filled:
            self._risk_manager.open_position(signal, quantity)
            self._audit.log_trade(
                trade_id=filled_order.order_id,
                symbol=signal.symbol,
                side=OrderSide.BUY.value,
                quantity=quantity,
                price=filled_order.filled_price or signal.price,
                strategy=signal.strategy_name,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                r_multiple=signal.r_multiple,
            )
            self._event_bus.publish_sync(
                Event(
                    type=EventType.ORDER_FILLED,
                    data={"order_id": filled_order.order_id, "symbol": signal.symbol},
                    source=signal.strategy_name,
                )
            )
        else:
            self._event_bus.publish_sync(
                Event(
                    type=EventType.ORDER_REJECTED,
                    data={"order_id": filled_order.order_id, "reason": "fill_failed"},
                    source=signal.strategy_name,
                )
            )

        return filled_order

    def _handle_sell_signal(self, signal: Signal) -> Optional[Order]:
        positions = self._risk_manager.positions
        if signal.symbol not in positions:
            logger.warning(
                "A-share 不支持做空，无持仓 %s，忽略卖出信号", signal.symbol
            )
            return None

        pos = positions[signal.symbol]
        if pos.side != PositionSide.LONG:
            logger.warning("A-share 不支持做空，%s 非多头仓位，忽略卖出信号", signal.symbol)
            return None

        if pos.is_t1_locked:
            logger.info("A-share T+1 锁定，%s 今日买入不可卖出", signal.symbol)
            return None

        order = Order(
            order_id="",
            symbol=signal.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=pos.quantity,
            price=signal.price,
            strategy_name=signal.strategy_name,
        )

        filled_order = self._broker.submit_order(order)

        if filled_order.is_filled:
            exit_price = filled_order.filled_price or signal.price
            result = self._risk_manager.close_position(
                signal.symbol, exit_price, reason="signal"
            )
            self._audit.log_trade(
                trade_id=filled_order.order_id,
                symbol=signal.symbol,
                side=OrderSide.SELL.value,
                quantity=pos.quantity,
                price=exit_price,
                strategy=signal.strategy_name,
                details={"pnl": result.get("pnl", 0), "reason": "signal"},
            )
            self._event_bus.publish_sync(
                Event(
                    type=EventType.POSITION_CLOSED,
                    data={"order_id": filled_order.order_id, "symbol": signal.symbol, "pnl": result.get("pnl", 0)},
                    source=signal.strategy_name,
                )
            )
        else:
            self._event_bus.publish_sync(
                Event(
                    type=EventType.ORDER_REJECTED,
                    data={"order_id": filled_order.order_id, "reason": "fill_failed"},
                    source=signal.strategy_name,
                )
            )

        return filled_order

    def check_stop_loss_take_profit(self, current_prices: dict[str, float]) -> list[dict]:
        for symbol, price in current_prices.items():
            self._risk_manager.update_price_history(symbol, price)

        closed = self._risk_manager.check_positions(current_prices)
        for trade in closed:
            side = OrderSide.SELL if trade["side"] == PositionSide.LONG else OrderSide.BUY
            order = Order(
                order_id="",
                symbol=trade["symbol"],
                side=side,
                order_type=OrderType.MARKET,
                quantity=trade.get("quantity", 0),
                price=trade["exit_price"],
                strategy_name=trade.get("strategy", ""),
            )
            self._broker.submit_order(order)
            self._audit.log_trade(
                trade_id=f"SL-{trade['symbol']}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                symbol=trade["symbol"],
                side=side.value,
                quantity=trade.get("quantity", 0),
                price=trade["exit_price"],
                strategy=trade.get("strategy", ""),
                details={"reason": trade["reason"], "pnl": trade["pnl"]},
            )
        return closed

    def get_portfolio_status(self) -> dict:
        balance = self._broker.get_account_balance()
        risk_state = self._risk_manager.get_state()
        positions_detail = {}
        for sym, pos in self._risk_manager.positions.items():
            positions_detail[sym] = {
                "side": pos.side,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "trailing_stop": pos.trailing_stop,
                "highest_price": pos.highest_price,
                "holding_days": pos.holding_days,
                "unrealized_pnl": pos.unrealized_pnl(
                    balance.get("total_equity", 0) / max(len(self._risk_manager.positions), 1)
                ),
            }
        return {
            "cash": balance["cash"],
            "total_equity": balance["total_equity"],
            "positions": positions_detail,
            "drawdown": risk_state.current_drawdown,
            "consecutive_losses": risk_state.consecutive_losses,
            "circuit_breaker": risk_state.is_circuit_breaker_active,
            "total_trades": risk_state.total_trades,
            "vol_multiplier": risk_state.vol_multiplier,
            "drawdown_multiplier": risk_state.drawdown_multiplier,
        }

    def start(self) -> None:
        self._running = True
        self._audit.log_action("engine_start", "system", {"mode": self._config.trading.mode})
        logger.info("Trading engine started in %s mode", self._config.trading.mode)

    def stop(self) -> None:
        self._running = False
        self._audit.log_action("engine_stop", "system", {})
        logger.info("Trading engine stopped")

    def run_loop(
        self,
        symbols: list[str],
        interval_seconds: int = 60,
        data_source: str = "akshare",
        on_cycle: Optional[callable] = None,
        enable_advisor: bool = False,
    ) -> None:
        self.start()
        logger.info(
            "Trading loop started: symbols=%s interval=%ds source=%s advisor=%s",
            symbols,
            interval_seconds,
            data_source,
            enable_advisor,
        )

        advisor = None
        tracker = None
        if enable_advisor:
            from trading_system.advisor.entry_exit import EntryExitAdvisor
            from trading_system.advisor.tracker import RecommendationTracker
            advisor = EntryExitAdvisor()
            tracker = RecommendationTracker()

        try:
            while self._running:
                cycle_start = time.time()

                if not self._trading_session.is_trading_time():
                    wait = self._trading_session.time_to_next_session()
                    if wait and wait.total_seconds() > 0:
                        logger.debug(
                            "Non-trading time, sleeping %ds until next session",
                            int(wait.total_seconds()),
                        )
                        sleep_time = min(wait.total_seconds(), interval_seconds * 5)
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                    continue

                try:
                    current_prices: dict[str, float] = {}
                    for symbol in symbols:
                        try:
                            rt = self._data_store.fetch_realtime(symbol, source=data_source)
                            price = rt.get("current_price", 0.0)
                            if price > 0:
                                current_prices[symbol] = price
                        except Exception as e:
                            logger.warning("Failed to fetch realtime for %s: %s", symbol, e)

                    if current_prices:
                        closed = self.check_stop_loss_take_profit(current_prices)
                        if closed:
                            logger.info("Closed %d positions in cycle", len(closed))

                    for symbol in symbols:
                        try:
                            df = self._data_store.fetch_daily(
                                symbol, source=data_source, use_cache=True
                            )
                            if df.empty:
                                continue

                            for name, strategy in self._strategies.items():
                                signals = strategy.generate_signals(df)
                                for sig in signals:
                                    sig.symbol = symbol
                                    self.process_signal(sig)

                            if enable_advisor and advisor and current_prices.get(symbol):
                                price = current_prices[symbol]
                                rec = advisor.recommend_entry(symbol, price, {})
                                if rec.recommendation_type.value == "买入" and tracker:
                                    tracker.record_recommendation(
                                        symbol=symbol,
                                        recommendation_type="买入",
                                        price=price,
                                        score=rec.score.total_score if rec.score else 0,
                                        rating=rec.score.rating.value if rec.score else "",
                                    )

                        except Exception as e:
                            logger.warning("Strategy cycle failed for %s: %s", symbol, e)

                    if on_cycle:
                        on_cycle(self)

                except Exception as e:
                    logger.error("Trading cycle error: %s", e)

                elapsed = time.time() - cycle_start
                sleep_time = max(0, interval_seconds - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Trading loop interrupted by user")
        finally:
            self.stop()
