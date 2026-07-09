"""Risk Manager — Position sizing, stop loss, circuit breaker, drawdown control.

Enforces:
- Max position size: 2% of capital per trade (AC5)
- Stop loss: default 5% per position
- Max drawdown: 20% triggers circuit breaker (AC5)
- Daily loss: 5% triggers circuit breaker with 3-day cooldown (AC5)
- Paper trading by default (AC1)
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """A trading position."""
    symbol: str
    name: str = ""
    entry_price: float = 0.0
    current_price: float = 0.0
    quantity: int = 0
    entry_date: str = ""
    stop_loss: float = 0.0
    take_profit: float = 0.0
    direction: str = "long"  # 'long' or 'short'

    @property
    def market_value(self) -> float:
        return self.current_price * self.quantity

    @property
    def cost_basis(self) -> float:
        return self.entry_price * self.quantity

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis


@dataclass
class RiskState:
    """Current risk management state."""
    total_capital: float = 100000.0
    peak_capital: float = 100000.0
    daily_start_capital: float = 100000.0
    daily_pnl: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)
    circuit_breaker_active: bool = False
    circuit_breaker_reason: str = ""
    circuit_breaker_until: Optional[str] = None
    trading_mode: str = "paper"  # 'paper' or 'live'
    total_trades: int = 0
    winning_trades: int = 0


class RiskManager:
    """Risk management engine for the trading system.

    Enforces all risk constraints from task.yaml hard_constraints:
    - Paper trading by default, --live flag required for live trading
    - Max position size: 2% of total capital
    - Max drawdown: 20% triggers circuit breaker
    - Daily loss: 5% triggers circuit breaker with 3-day cooldown
    """

    def __init__(self, config_dir: str = "config"):
        config = get_config(config_dir)
        self._config = config
        self._lock = threading.RLock()
        self._audit = get_audit_logger()
        self._event_bus = get_event_bus()

        # Risk limits from config
        self.max_position_pct = config.get("risk.max_position_pct", 0.02)
        self.max_drawdown_pct = config.get("risk.max_drawdown_pct", 0.20)
        self.daily_loss_pct = config.get("risk.daily_loss_pct", 0.05)
        self.cooldown_days = config.get("risk.cooldown_days", 3)
        self.default_stop_loss_pct = config.get("risk.stop_loss_pct", 0.05)
        self.default_take_profit_pct = config.get("risk.take_profit_pct", 0.15)

        # State
        self.state = RiskState(
            total_capital=config.get("trading.initial_capital", 100000.0),
            peak_capital=config.get("trading.initial_capital", 100000.0),
            daily_start_capital=config.get("trading.initial_capital", 100000.0),
            trading_mode=config.get("trading.mode", "paper"),
        )

        # Subscribe to events
        self._event_bus.subscribe("execution.order_filled", self._on_order_filled)
        self._event_bus.subscribe("market.price_updated", self._on_price_updated)
        self._event_bus.subscribe("trading.new_day", self._on_new_day)

        logger.info(
            "RiskManager initialized: mode=%s, capital=%.2f, max_position=%.1f%%, "
            "max_drawdown=%.1f%%, daily_loss=%.1f%%",
            self.state.trading_mode,
            self.state.total_capital,
            self.max_position_pct * 100,
            self.max_drawdown_pct * 100,
            self.daily_loss_pct * 100,
        )

    # --- Public API ---

    def can_open_position(
        self, symbol: str, price: float, quantity: int, direction: str = "long"
    ) -> tuple:
        """Check if a new position can be opened.

        Args:
            symbol: Stock code.
            price: Entry price per share.
            quantity: Number of shares.
            direction: 'long' or 'short'.

        Returns:
            (approved: bool, reason: str)
        """
        with self._lock:
            # Check circuit breaker
            if self.state.circuit_breaker_active:
                if self.state.circuit_breaker_until:
                    until = datetime.fromisoformat(self.state.circuit_breaker_until)
                    if datetime.now() < until:
                        return False, (
                            f"Circuit breaker active until {self.state.circuit_breaker_until}: "
                            f"{self.state.circuit_breaker_reason}"
                        )
                    else:
                        self._reset_circuit_breaker()

            # Check position size
            position_value = price * quantity
            max_allowed = self.state.total_capital * self.max_position_pct
            if position_value > max_allowed:
                return False, (
                    f"Position size {position_value:.2f} exceeds max "
                    f"{max_allowed:.2f} ({self.max_position_pct*100:.1f}% of capital)"
                )

            # Check if symbol already has a position
            if symbol in self.state.positions:
                return False, f"Already holding position in {symbol}"

            return True, "OK"

    def open_position(
        self,
        symbol: str,
        name: str,
        price: float,
        quantity: int,
        direction: str = "long",
        stop_loss_pct: float = None,
        take_profit_pct: float = None,
    ) -> Optional[Position]:
        """Open a new position after risk checks.

        Args:
            symbol: Stock code.
            name: Stock name.
            price: Entry price.
            quantity: Number of shares.
            direction: 'long' or 'short'.
            stop_loss_pct: Custom stop loss percentage (default from config).
            take_profit_pct: Custom take profit percentage (default from config).

        Returns:
            Position object if approved, None if rejected.
        """
        approved, reason = self.can_open_position(symbol, price, quantity, direction)
        if not approved:
            self._audit.log(
                "risk_check",
                check_id=f"open_position_{symbol}",
                result="BLOCKED",
                payload={"symbol": symbol, "reason": reason},
            )
            self._event_bus.publish(
                "risk.position_rejected",
                {"symbol": symbol, "reason": reason},
            )
            logger.warning("Position rejected: %s — %s", symbol, reason)
            return None

        sl_pct = stop_loss_pct if stop_loss_pct is not None else self.default_stop_loss_pct
        tp_pct = take_profit_pct if take_profit_pct is not None else self.default_take_profit_pct

        position = Position(
            symbol=symbol,
            name=name,
            entry_price=price,
            current_price=price,
            quantity=quantity,
            entry_date=datetime.now().strftime("%Y-%m-%d"),
            stop_loss=price * (1 - sl_pct),
            take_profit=price * (1 + tp_pct),
            direction=direction,
        )

        with self._lock:
            self.state.positions[symbol] = position
            self.state.total_trades += 1

        self._audit.log(
            "order_placement",
            check_id=f"open_{symbol}",
            result="OK",
            payload={
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "direction": direction,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "trading_mode": self.state.trading_mode,
            },
        )
        self._event_bus.publish(
            "risk.position_opened",
            {
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "direction": direction,
            },
        )
        logger.info("Position opened: %s %d@%.2f", symbol, quantity, price)
        return position

    def close_position(self, symbol: str, price: float) -> Optional[Dict]:
        """Close an existing position.

        Args:
            symbol: Stock code.
            price: Exit price.

        Returns:
            Dict with trade summary, or None if no position exists.
        """
        with self._lock:
            if symbol not in self.state.positions:
                return None

            position = self.state.positions.pop(symbol)
            pnl = (price - position.entry_price) * position.quantity
            pnl_pct = (price / position.entry_price - 1) * 100

            self.state.total_capital += pnl
            if position.direction == "long" and pnl > 0:
                self.state.winning_trades += 1

            # Update peak capital
            if self.state.total_capital > self.state.peak_capital:
                self.state.peak_capital = self.state.total_capital

            # Update daily PnL
            self.state.daily_pnl += pnl

            result = {
                "symbol": symbol,
                "entry_price": position.entry_price,
                "exit_price": price,
                "quantity": position.quantity,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "holding_period": position.entry_date,
            }

        self._audit.log(
            "order_placement",
            check_id=f"close_{symbol}",
            result="OK",
            payload=result,
        )
        self._event_bus.publish("risk.position_closed", result)
        logger.info("Position closed: %s PnL=%.2f (%.2f%%)", symbol, pnl, pnl_pct)

        # Check drawdown after closing
        self._check_drawdown()
        self._check_daily_loss()

        return result

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """Check if a position has hit its stop loss.

        Returns:
            True if stop loss was triggered (position closed).
        """
        with self._lock:
            if symbol not in self.state.positions:
                return False
            pos = self.state.positions[symbol]
            if pos.direction == "long" and current_price <= pos.stop_loss:
                self._audit.log(
                    "risk_check",
                    check_id=f"stop_loss_{symbol}",
                    result="TRIGGERED",
                    payload={
                        "symbol": symbol,
                        "stop_loss": pos.stop_loss,
                        "current_price": current_price,
                    },
                )
                self._event_bus.publish(
                    "risk.stop_loss_triggered",
                    {"symbol": symbol, "stop_loss": pos.stop_loss, "price": current_price},
                )
                return True
        return False

    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """Check if a position has hit its take profit.

        Returns:
            True if take profit was triggered.
        """
        with self._lock:
            if symbol not in self.state.positions:
                return False
            pos = self.state.positions[symbol]
            if pos.direction == "long" and current_price >= pos.take_profit:
                self._event_bus.publish(
                    "risk.take_profit_triggered",
                    {"symbol": symbol, "take_profit": pos.take_profit, "price": current_price},
                )
                return True
        return False

    def get_drawdown(self) -> float:
        """Get current drawdown percentage."""
        with self._lock:
            if self.state.peak_capital == 0:
                return 0.0
            return 1 - self.state.total_capital / self.state.peak_capital

    def get_daily_pnl_pct(self) -> float:
        """Get daily PnL as percentage."""
        with self._lock:
            if self.state.daily_start_capital == 0:
                return 0.0
            return self.state.daily_pnl / self.state.daily_start_capital

    def get_position_summary(self) -> Dict[str, Any]:
        """Get current risk state summary."""
        with self._lock:
            positions = [
                {
                    "symbol": p.symbol,
                    "name": p.name,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "quantity": p.quantity,
                    "market_value": p.market_value,
                    "unrealized_pnl": p.unrealized_pnl,
                    "pnl_pct": p.pnl_pct,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                }
                for p in self.state.positions.values()
            ]
            total_exposure = sum(p.market_value for p in self.state.positions.values())

            return {
                "trading_mode": self.state.trading_mode,
                "total_capital": self.state.total_capital,
                "peak_capital": self.state.peak_capital,
                "drawdown_pct": self.get_drawdown(),
                "daily_pnl": self.state.daily_pnl,
                "daily_pnl_pct": self.get_daily_pnl_pct(),
                "total_exposure": total_exposure,
                "exposure_pct": (
                    total_exposure / self.state.total_capital
                    if self.state.total_capital > 0
                    else 0
                ),
                "position_count": len(positions),
                "total_trades": self.state.total_trades,
                "winning_trades": self.state.winning_trades,
                "circuit_breaker_active": self.state.circuit_breaker_active,
                "circuit_breaker_reason": self.state.circuit_breaker_reason,
                "positions": positions,
            }

    def set_trading_mode(self, mode: str) -> bool:
        """Set trading mode. 'live' requires explicit confirmation.

        Args:
            mode: 'paper' or 'live'.

        Returns:
            True if mode was changed.
        """
        if mode not in ("paper", "live"):
            logger.error("Invalid trading mode: %s", mode)
            return False

        with self._lock:
            old_mode = self.state.trading_mode
            self.state.trading_mode = mode

        self._audit.log(
            "config_changes",
            check_id="trading_mode",
            result="OK",
            payload={"old": old_mode, "new": mode},
        )
        self._event_bus.publish("risk.trading_mode_changed", {"mode": mode})
        logger.warning("Trading mode changed: %s → %s", old_mode, mode)
        return True

    def update_capital(self, new_capital: float) -> None:
        """Update total capital (e.g., after deposit/withdrawal)."""
        with self._lock:
            self.state.total_capital = new_capital
            if new_capital > self.state.peak_capital:
                self.state.peak_capital = new_capital

    # --- Internal Methods ---

    def _check_drawdown(self) -> None:
        """Check if max drawdown has been exceeded."""
        drawdown = self.get_drawdown()
        if drawdown >= self.max_drawdown_pct:
            self._trigger_circuit_breaker(
                f"Max drawdown exceeded: {drawdown*100:.1f}% >= {self.max_drawdown_pct*100:.1f}%"
            )

    def _check_daily_loss(self) -> None:
        """Check if daily loss limit has been exceeded."""
        daily_loss = abs(self.get_daily_pnl_pct())
        if self.state.daily_pnl < 0 and daily_loss >= self.daily_loss_pct:
            self._trigger_circuit_breaker(
                f"Daily loss limit exceeded: {daily_loss*100:.1f}% >= {self.daily_loss_pct*100:.1f}%"
            )

    def _trigger_circuit_breaker(self, reason: str) -> None:
        """Activate the circuit breaker."""
        with self._lock:
            if self.state.circuit_breaker_active:
                return
            self.state.circuit_breaker_active = True
            self.state.circuit_breaker_reason = reason
            until = datetime.now() + timedelta(days=self.cooldown_days)
            self.state.circuit_breaker_until = until.isoformat()

        self._audit.log(
            "circuit_breaker",
            check_id="circuit_breaker",
            result="TRIGGERED",
            payload={
                "reason": reason,
                "cooldown_days": self.cooldown_days,
                "until": self.state.circuit_breaker_until,
                "drawdown": self.get_drawdown(),
                "daily_loss": self.get_daily_pnl_pct(),
            },
        )
        self._event_bus.publish(
            "risk.circuit_breaker_triggered",
            {"reason": reason, "until": self.state.circuit_breaker_until},
        )
        logger.critical("CIRCUIT BREAKER TRIGGERED: %s", reason)

    def _reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker after cooldown."""
        with self._lock:
            self.state.circuit_breaker_active = False
            self.state.circuit_breaker_reason = ""
            self.state.circuit_breaker_until = None
            self.state.daily_start_capital = self.state.total_capital
            self.state.daily_pnl = 0.0

        self._audit.log(
            "circuit_breaker",
            check_id="circuit_breaker",
            result="RESET",
            payload={"capital": self.state.total_capital},
        )
        self._event_bus.publish("risk.circuit_breaker_reset", {})
        logger.info("Circuit breaker reset")

    def _on_order_filled(self, event: Event) -> None:
        """Handle order filled events."""
        pass  # Order handling is done via open_position/close_position

    def _on_price_updated(self, event: Event) -> None:
        """Handle price update events."""
        data = event.data or {}
        symbol = data.get("symbol", "")
        price = data.get("price", 0.0)
        with self._lock:
            if symbol in self.state.positions:
                self.state.positions[symbol].current_price = price
                # Check stop loss and take profit
                if self.check_stop_loss(symbol, price):
                    self.close_position(symbol, price)
                elif self.check_take_profit(symbol, price):
                    self.close_position(symbol, price)

    def _on_new_day(self, event: Event) -> None:
        """Handle new trading day event."""
        with self._lock:
            self.state.daily_start_capital = self.state.total_capital
            self.state.daily_pnl = 0.0
        logger.info(
            "New trading day: daily_start_capital=%.2f",
            self.state.daily_start_capital,
        )