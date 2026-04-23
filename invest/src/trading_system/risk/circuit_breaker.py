import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class BreakerType(Enum):
    DAILY_LOSS = "daily_loss"
    TOTAL_DRAWDOWN = "total_drawdown"
    ORDER_FREQUENCY = "order_frequency"
    CONCENTRATION = "concentration"


class BreakerStatus(Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    COOLDOWN = "cooldown"


@dataclass
class BreakerEvent:
    breaker_type: BreakerType
    status: BreakerStatus
    triggered_at: datetime
    value: float
    threshold: float
    message: str


@dataclass
class BreakerConfig:
    daily_loss_pct: float = 0.03
    total_drawdown_pct: float = 0.10
    order_frequency_limit: int = 5
    order_frequency_window_seconds: int = 60
    concentration_pct: float = 0.30
    cooldown_minutes: int = 30


class CircuitBreaker:
    def __init__(
        self,
        config: Optional[BreakerConfig] = None,
        notification_manager=None,
    ):
        self._config = config or BreakerConfig()
        self._notification = notification_manager
        self._status: dict[BreakerType, BreakerStatus] = {
            bt: BreakerStatus.INACTIVE for bt in BreakerType
        }
        self._triggered_at: dict[BreakerType, Optional[datetime]] = {
            bt: None for bt in BreakerType
        }
        self._events: list[BreakerEvent] = []
        self._order_timestamps: list[datetime] = []
        self._daily_loss: float = 0.0
        self._initial_capital: float = 0.0
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0

    @property
    def is_any_active(self) -> bool:
        return any(s == BreakerStatus.ACTIVE for s in self._status.values())

    @property
    def active_breakers(self) -> list[BreakerType]:
        return [bt for bt, s in self._status.items() if s == BreakerStatus.ACTIVE]

    @property
    def events(self) -> list[BreakerEvent]:
        return list(self._events)

    def initialize(self, initial_capital: float) -> None:
        self._initial_capital = initial_capital
        self._peak_equity = initial_capital
        self._current_equity = initial_capital

    def update_equity(self, equity: float) -> None:
        self._current_equity = equity
        if equity > self._peak_equity:
            self._peak_equity = equity

    def update_daily_loss(self, loss: float) -> None:
        self._daily_loss += min(0, loss)

    def reset_daily(self) -> None:
        self._daily_loss = 0.0
        for bt in [BreakerType.DAILY_LOSS, BreakerType.ORDER_FREQUENCY]:
            if self._status[bt] == BreakerStatus.ACTIVE:
                self._deactivate(bt)

    def record_order(self) -> None:
        now = datetime.now()
        self._order_timestamps.append(now)
        cutoff = now - timedelta(seconds=self._config.order_frequency_window_seconds)
        self._order_timestamps = [t for t in self._order_timestamps if t >= cutoff]

    def check_daily_loss(self) -> bool:
        if self._initial_capital <= 0:
            return False
        loss_pct = abs(self._daily_loss) / self._initial_capital
        if loss_pct >= self._config.daily_loss_pct:
            self._activate(BreakerType.DAILY_LOSS, loss_pct, self._config.daily_loss_pct)
            return True
        return False

    def check_total_drawdown(self) -> bool:
        if self._peak_equity <= 0:
            return False
        drawdown = (self._peak_equity - self._current_equity) / self._peak_equity
        if drawdown >= self._config.total_drawdown_pct:
            self._activate(BreakerType.TOTAL_DRAWDOWN, drawdown, self._config.total_drawdown_pct)
            return True
        return False

    def check_order_frequency(self) -> bool:
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._config.order_frequency_window_seconds)
        recent = [t for t in self._order_timestamps if t >= cutoff]
        if len(recent) > self._config.order_frequency_limit:
            self._activate(
                BreakerType.ORDER_FREQUENCY, len(recent), self._config.order_frequency_limit
            )
            return True
        return False

    def check_concentration(self, symbol_value: float, total_equity: float) -> bool:
        if total_equity <= 0:
            return False
        concentration = symbol_value / total_equity
        if concentration >= self._config.concentration_pct:
            self._activate(BreakerType.CONCENTRATION, concentration, self._config.concentration_pct)
            return True
        return False

    def check_all(self, symbol_value: float = 0.0, total_equity: float = 0.0) -> bool:
        triggered = False
        if self.check_daily_loss():
            triggered = True
        if self.check_total_drawdown():
            triggered = True
        if self.check_order_frequency():
            triggered = True
        if symbol_value > 0 and total_equity > 0:
            if self.check_concentration(symbol_value, total_equity):
                triggered = True
        return triggered

    def can_open_position(self) -> bool:
        if self._status[BreakerType.DAILY_LOSS] == BreakerStatus.ACTIVE:
            return False
        if self._status[BreakerType.TOTAL_DRAWDOWN] == BreakerStatus.ACTIVE:
            return False
        if self._status[BreakerType.ORDER_FREQUENCY] == BreakerStatus.ACTIVE:
            return False
        return True

    def can_buy_symbol(self, symbol_value: float, total_equity: float) -> bool:
        if not self.can_open_position():
            return False
        if symbol_value > 0 and total_equity > 0:
            concentration = symbol_value / total_equity
            if concentration >= self._config.concentration_pct:
                return False
        return True

    def can_trade_at_all(self) -> bool:
        if self._status[BreakerType.TOTAL_DRAWDOWN] == BreakerStatus.ACTIVE:
            return False
        return True

    def reset(self, breaker_type: BreakerType, confirm: bool = False) -> bool:
        if not confirm:
            logger.warning("Reset requires confirmation: confirm=True")
            return False
        self._deactivate(breaker_type)
        return True

    def reset_all(self, confirm: bool = False) -> bool:
        if not confirm:
            logger.warning("Reset all requires confirmation: confirm=True")
            return False
        for bt in BreakerType:
            self._deactivate(bt)
        return True

    def _activate(self, breaker_type: BreakerType, value: float, threshold: float) -> None:
        if self._status[breaker_type] == BreakerStatus.ACTIVE:
            return
        self._status[breaker_type] = BreakerStatus.ACTIVE
        self._triggered_at[breaker_type] = datetime.now()

        messages = {
            BreakerType.DAILY_LOSS: f"单日亏损熔断触发：亏损 {value:.2%}，阈值 {threshold:.2%}",
            BreakerType.TOTAL_DRAWDOWN: f"总回撤熔断触发：回撤 {value:.2%}，阈值 {threshold:.2%}",
            BreakerType.ORDER_FREQUENCY: f"下单频率熔断触发：{int(value)}笔/分钟，阈值 {int(threshold)}笔/分钟",
            BreakerType.CONCENTRATION: f"单股集中度熔断触发：集中度 {value:.2%}，阈值 {threshold:.2%}",
        }
        msg = messages.get(breaker_type, f"熔断触发: {breaker_type.value}")

        event = BreakerEvent(
            breaker_type=breaker_type,
            status=BreakerStatus.ACTIVE,
            triggered_at=datetime.now(),
            value=value,
            threshold=threshold,
            message=msg,
        )
        self._events.append(event)

        logger.warning("CIRCUIT BREAKER: %s", msg)

        if self._notification:
            from trading_system.notification.channels import NotificationLevel, NotificationMessage
            self._notification.notify(
                NotificationMessage(
                    title=f"熔断触发: {breaker_type.value}",
                    content=msg,
                    level=NotificationLevel.CRITICAL,
                    source="硬风控熔断",
                )
            )

    def _deactivate(self, breaker_type: BreakerType) -> None:
        if self._status[breaker_type] == BreakerStatus.INACTIVE:
            return
        self._status[breaker_type] = BreakerStatus.INACTIVE
        self._triggered_at[breaker_type] = None
        logger.info("Circuit breaker deactivated: %s", breaker_type.value)

    def get_status(self) -> dict:
        return {
            "is_any_active": self.is_any_active,
            "active_breakers": [bt.value for bt in self.active_breakers],
            "daily_loss": self._daily_loss,
            "daily_loss_pct": abs(self._daily_loss) / self._initial_capital if self._initial_capital > 0 else 0,
            "current_equity": self._current_equity,
            "peak_equity": self._peak_equity,
            "drawdown_pct": (self._peak_equity - self._current_equity) / self._peak_equity if self._peak_equity > 0 else 0,
            "breakers": {
                bt.value: {
                    "status": self._status[bt].value,
                    "triggered_at": self._triggered_at[bt].isoformat() if self._triggered_at[bt] else None,
                }
                for bt in BreakerType
            },
        }
