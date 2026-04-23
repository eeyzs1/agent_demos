import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from trading_system.core.config import RiskConfig
from trading_system.risk.sizer import PositionSizer
from trading_system.strategy.base import PositionSide, Signal, SignalType

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: datetime = field(default_factory=datetime.now)
    strategy_name: str = ""
    risk_amount: float = 0.0
    trailing_stop: Optional[float] = None
    highest_price: float = 0.0
    lowest_price: float = float("inf")
    trailing_stop_pct: float = 0.05
    trailing_stop_activate_pct: float = 0.03
    max_holding_days: int = 30
    commission: float = 0.0
    is_t1_locked: bool = True

    @property
    def current_value(self) -> float:
        return self.quantity * self.entry_price

    def holding_days_at(self, reference_time: Optional[datetime] = None) -> int:
        ref = reference_time or datetime.now()
        return (ref - self.entry_time).days

    def is_t1_locked_on(self, reference_time: Optional[datetime] = None) -> bool:
        ref = reference_time or datetime.now()
        return (ref.date() - self.entry_time.date()).days == 0

    def unlock_t1(self, reference_time: Optional[datetime] = None) -> None:
        if not self.is_t1_locked_on(reference_time):
            self.is_t1_locked = False

    @property
    def holding_days(self) -> int:
        return self.holding_days_at()

    def unrealized_pnl(self, current_price: float) -> float:
        if self.side == PositionSide.LONG:
            return (current_price - self.entry_price) * self.quantity
        return (self.entry_price - current_price) * self.quantity

    def should_stop_loss(self, current_price: float) -> bool:
        if self.side == PositionSide.LONG:
            return current_price <= self.stop_loss
        return current_price >= self.stop_loss

    def should_take_profit(self, current_price: float) -> bool:
        if self.side == PositionSide.LONG:
            return current_price >= self.take_profit
        return current_price <= self.take_profit

    def should_trailing_stop(self, current_price: float) -> bool:
        if self.trailing_stop is None:
            return False
        if self.side == PositionSide.LONG:
            return current_price <= self.trailing_stop
        return current_price >= self.trailing_stop

    def should_timeout(self) -> bool:
        return self.holding_days >= self.max_holding_days

    def update_trailing_stop(self, current_price: float) -> None:
        if self.side == PositionSide.LONG:
            if current_price > self.highest_price:
                self.highest_price = current_price
            profit_pct = (self.highest_price - self.entry_price) / self.entry_price
            if profit_pct >= self.trailing_stop_activate_pct:
                new_trail = self.highest_price * (1 - self.trailing_stop_pct)
                if self.trailing_stop is None or new_trail > self.trailing_stop:
                    self.trailing_stop = new_trail
                    logger.debug(
                        "Trailing stop updated for %s: %.2f (highest=%.2f)",
                        self.symbol,
                        self.trailing_stop,
                        self.highest_price,
                    )
        else:
            if current_price < self.lowest_price:
                self.lowest_price = current_price
            profit_pct = (self.entry_price - self.lowest_price) / self.entry_price
            if profit_pct >= self.trailing_stop_activate_pct:
                new_trail = self.lowest_price * (1 + self.trailing_stop_pct)
                if self.trailing_stop is None or new_trail < self.trailing_stop:
                    self.trailing_stop = new_trail
                    logger.debug(
                        "Trailing stop updated for %s: %.2f (lowest=%.2f)",
                        self.symbol,
                        self.trailing_stop,
                        self.lowest_price,
                    )


@dataclass
class RiskState:
    equity: float
    peak_equity: float
    current_drawdown: float
    consecutive_losses: int
    daily_loss: float
    daily_trades: int
    total_trades: int
    is_circuit_breaker_active: bool
    circuit_breaker_until: Optional[datetime] = None
    vol_multiplier: float = 1.0
    drawdown_multiplier: float = 1.0


class RiskManager:
    def __init__(self, config: RiskConfig, initial_capital: float):
        self._config = config
        self._initial_capital = initial_capital
        self._positions: dict[str, Position] = {}
        self._equity = initial_capital
        self._peak_equity = initial_capital
        self._consecutive_losses = 0
        self._daily_loss = 0.0
        self._daily_trades = 0
        self._total_trades = 0
        self._circuit_breaker_active = False
        self._circuit_breaker_until: Optional[datetime] = None
        self._closed_trades: list[dict] = []
        self._sizer = PositionSizer(config, initial_capital)

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def current_drawdown(self) -> float:
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - self._equity) / self._peak_equity

    @property
    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def get_state(self) -> RiskState:
        return RiskState(
            equity=self._equity,
            peak_equity=self._peak_equity,
            current_drawdown=self.current_drawdown,
            consecutive_losses=self._consecutive_losses,
            daily_loss=self._daily_loss,
            daily_trades=self._daily_trades,
            total_trades=self._total_trades,
            is_circuit_breaker_active=self._circuit_breaker_active,
            circuit_breaker_until=self._circuit_breaker_until,
            vol_multiplier=self._sizer.calc_vol_multiplier(),
            drawdown_multiplier=PositionSizer.calc_drawdown_multiplier(
                self.current_drawdown, self._config
            ),
        )

    def update_price_history(self, symbol: str, price: float) -> None:
        self._sizer.update_price_history(symbol, price)

    def calculate_position_size(self, signal: Signal) -> float:
        return self._sizer.calculate_position_size(
            equity=self._equity,
            signal=signal,
            current_drawdown=self.current_drawdown,
        )

    def validate_signal(self, signal: Signal) -> tuple[bool, str]:
        if self._circuit_breaker_active:
            if self._circuit_breaker_until and datetime.now() >= self._circuit_breaker_until:
                self._deactivate_circuit_breaker()
            else:
                return False, "Circuit breaker is active - trading suspended"

        if self.current_drawdown >= self._config.max_drawdown_limit:
            self._activate_circuit_breaker()
            return False, f"Max drawdown limit reached: {self.current_drawdown:.2%}"

        if self._consecutive_losses >= self._config.max_consecutive_losses:
            return False, f"Max consecutive losses reached: {self._consecutive_losses}"

        if signal.stop_loss is None:
            return False, "Signal must have a stop-loss"

        if signal.risk_reward_ratio < 1.0:
            return False, f"Risk/reward ratio too low: {signal.risk_reward_ratio:.2f}"

        if signal.confidence < self._config.min_confidence:
            return (
                False,
                f"Signal confidence too low: "
                f"{signal.confidence:.2f} < {self._config.min_confidence}",
            )

        if signal.signal_type == SignalType.BUY and signal.symbol in self._positions:
            existing = self._positions[signal.symbol]
            if existing.side == "long":
                return False, f"Already have long position in {signal.symbol}"

        if signal.signal_type == SignalType.SELL and signal.symbol in self._positions:
            existing = self._positions[signal.symbol]
            if existing.side == "short":
                return False, f"Already have short position in {signal.symbol}"

        position_size = self.calculate_position_size(signal)
        position_value = position_size * signal.price
        total_exposure = sum(p.current_value for p in self._positions.values()) + position_value
        if total_exposure > self._equity * 0.8:
            return False, "Total exposure would exceed 80% of equity"

        dd_mult = PositionSizer.calc_drawdown_multiplier(self.current_drawdown, self._config)
        if dd_mult <= 0:
            return False, "Drawdown de-risk active: position multiplier is 0"

        return True, "Signal validated"

    def open_position(self, signal: Signal, quantity: float) -> Position:
        position = Position(
            symbol=signal.symbol,
            side=PositionSide.from_signal(signal.signal_type),
            quantity=quantity,
            entry_price=signal.price,
            stop_loss=signal.stop_loss or signal.price * 0.95,
            take_profit=signal.take_profit or signal.price * 1.15,
            strategy_name=signal.strategy_name,
            risk_amount=abs(signal.price - (signal.stop_loss or signal.price * 0.95)) * quantity,
            trailing_stop_pct=self._config.trailing_stop_pct,
            trailing_stop_activate_pct=self._config.trailing_stop_activate_pct,
            max_holding_days=self._config.max_holding_days,
            highest_price=signal.price if signal.signal_type == SignalType.BUY else 0.0,
            lowest_price=signal.price if signal.signal_type == SignalType.SELL else float("inf"),
        )
        self._positions[signal.symbol] = position
        self._total_trades += 1
        self._daily_trades += 1
        logger.info(
            "Position opened: %s %s %s@%s SL=%s TP=%s trail_pct=%.0f%% max_days=%d",
            position.side,
            position.symbol,
            position.quantity,
            position.entry_price,
            position.stop_loss,
            position.take_profit,
            position.trailing_stop_pct * 100,
            position.max_holding_days,
        )
        return position

    def close_position(self, symbol: str, exit_price: float, reason: str = "") -> dict:
        if symbol not in self._positions:
            raise ValueError(f"No position found for {symbol}")

        position = self._positions.pop(symbol)
        pnl = position.unrealized_pnl(exit_price)
        pnl_pct = (
            pnl / (position.entry_price * position.quantity)
            if position.entry_price * position.quantity > 0
            else 0
        )

        r_multiple = pnl / position.risk_amount if position.risk_amount > 0 else 0

        self._equity += pnl

        if pnl > 0:
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1

        self._daily_loss += min(0, pnl)

        if self._equity > self._peak_equity:
            self._peak_equity = self._equity

        if abs(self._daily_loss) / self._initial_capital >= self._config.circuit_breaker_loss_pct:
            self._activate_circuit_breaker()

        trail_info = ""
        if position.trailing_stop is not None:
            trail_info = f" trail_stop={position.trailing_stop:.2f}"

        trade_record = {
            "symbol": symbol,
            "side": position.side,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "quantity": position.quantity,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "r_multiple": r_multiple,
            "reason": reason,
            "strategy": position.strategy_name,
            "entry_time": position.entry_time.isoformat(),
            "exit_time": datetime.now().isoformat(),
            "holding_days": position.holding_days,
            "trailing_stop": position.trailing_stop,
        }
        self._closed_trades.append(trade_record)

        logger.info(
            "Position closed: %s %s@%s→%s PnL=%.2f R=%.2f reason=%s hold=%dd%s",
            position.side,
            symbol,
            position.entry_price,
            exit_price,
            pnl,
            r_multiple,
            reason,
            position.holding_days,
            trail_info,
        )
        return trade_record

    def check_positions(self, current_prices: dict[str, float]) -> list[dict]:
        closed = []
        for symbol, position in list(self._positions.items()):
            price = current_prices.get(symbol)
            if price is None:
                continue

            position.unlock_t1()
            position.update_trailing_stop(price)

            if position.is_t1_locked:
                continue

            if position.should_trailing_stop(price):
                result = self.close_position(symbol, price, "trailing_stop")
                closed.append(result)
            elif position.should_stop_loss(price):
                result = self.close_position(symbol, price, "stop_loss")
                closed.append(result)
            elif position.should_take_profit(price):
                result = self.close_position(symbol, price, "take_profit")
                closed.append(result)
            elif position.should_timeout():
                result = self.close_position(symbol, price, "timeout")
                closed.append(result)

        return closed

    def _activate_circuit_breaker(self) -> None:
        self._circuit_breaker_active = True
        self._circuit_breaker_until = datetime.now() + timedelta(
            days=self._config.circuit_breaker_cooldown_days
        )
        logger.warning(
            "CIRCUIT BREAKER ACTIVATED until %s. Daily loss: %.2f, Drawdown: %.2f%%",
            self._circuit_breaker_until,
            self._daily_loss,
            self.current_drawdown * 100,
        )

    def _deactivate_circuit_breaker(self) -> None:
        self._circuit_breaker_active = False
        self._circuit_breaker_until = None
        self._daily_loss = 0.0
        self._daily_trades = 0
        logger.info("Circuit breaker deactivated - trading resumed")

    def reset_daily(self) -> None:
        self._daily_loss = 0.0
        self._daily_trades = 0

    def get_closed_trades(self) -> list[dict]:
        return list(self._closed_trades)
