"""EventBus — Central event dispatch for inter-module communication.

All inter-module communication goes through EventBus, not direct imports (AR001).
"""

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """An event dispatched through the EventBus."""
    event_type: str
    data: Any = None
    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    id: str = ""


class EventBus:
    """Publish-subscribe event bus for inter-module communication.

    All modules communicate through the EventBus. No direct imports between
    modules except through core (AR001, AR002).
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._event_counter = 0
        self._history: List[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Register a handler for an event type.

        Args:
            event_type: The event type string to listen for. Use '*' for all events.
            handler: Callable that receives an Event object.
        """
        with self._lock:
            self._handlers[event_type].append(handler)
            logger.debug("Subscribed handler for event_type=%s", event_type)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Remove a handler registration."""
        with self._lock:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

    def publish(self, event_type: str, data: Any = None, source: str = "") -> Event:
        """Publish an event to all registered handlers.

        Args:
            event_type: The event type string.
            data: Optional payload data.
            source: Optional source module identifier.

        Returns:
            The published Event object.
        """
        with self._lock:
            self._event_counter += 1
            event = Event(
                event_type=event_type,
                data=data,
                source=source,
                id=f"evt_{self._event_counter:06d}",
            )
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        handlers = []
        with self._lock:
            handlers = list(self._handlers.get(event_type, [])) + list(
                self._handlers.get("*", [])
            )

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Handler %s failed for event %s", handler, event_type
                )

        return event

    def get_history(self, event_type: str = None, limit: int = 100) -> List[Event]:
        """Get recent event history.

        Args:
            event_type: Optional filter by event type.
            limit: Maximum number of events to return.

        Returns:
            List of Event objects.
        """
        with self._lock:
            events = list(self._history)
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            return events[-limit:]


# Global singleton
_event_bus: EventBus = None


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus