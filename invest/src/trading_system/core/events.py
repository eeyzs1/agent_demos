import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    MARKET_DATA = "market_data"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_CREATED = "order_created"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    RISK_ALERT = "risk_alert"
    CIRCUIT_BREAKER = "circuit_breaker"
    STRATEGY_START = "strategy_start"
    STRATEGY_STOP = "strategy_stop"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    DRAWDOWN_WARNING = "drawdown_warning"
    SYSTEM_ERROR = "system_error"


@dataclass
class Event:
    type: EventType
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "data": str(self.data),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


class EventBus:
    def __init__(self):
        self._handlers: dict[EventType, list[Callable]] = {}
        self._history: list[Event] = []
        self._max_history = 10000

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("Subscribed handler %s to %s", handler.__name__, event_type.value)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    async def publish(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "Handler %s failed for event %s: %s",
                    handler.__name__,
                    event.type.value,
                    e,
                )

    def publish_sync(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Handler %s failed for event %s: %s",
                    handler.__name__,
                    event.type.value,
                    e,
                )

    def get_history(self, event_type: EventType | None = None) -> list[Event]:
        if event_type:
            return [e for e in self._history if e.type == event_type]
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()
