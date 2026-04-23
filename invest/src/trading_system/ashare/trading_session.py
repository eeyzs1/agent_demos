import logging
from datetime import date, datetime, time, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)

CHINA_HOLIDAYS_2024 = {
    date(2024, 1, 1),
    date(2024, 2, 9), date(2024, 2, 10), date(2024, 2, 11),
    date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14),
    date(2024, 2, 15), date(2024, 2, 16), date(2024, 2, 17),
    date(2024, 4, 4), date(2024, 4, 5), date(2024, 4, 6),
    date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3),
    date(2024, 5, 4), date(2024, 5, 5),
    date(2024, 6, 8), date(2024, 6, 9), date(2024, 6, 10),
    date(2024, 9, 15), date(2024, 9, 16), date(2024, 9, 17),
    date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3),
    date(2024, 10, 4), date(2024, 10, 5), date(2024, 10, 6),
    date(2024, 10, 7),
}

CHINA_HOLIDAYS_2025 = {
    date(2025, 1, 1),
    date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2),
    date(2025, 2, 3), date(2025, 2, 4),
    date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 6),
    date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3),
    date(2025, 5, 4), date(2025, 5, 5),
    date(2025, 5, 31), date(2025, 6, 1), date(2025, 6, 2),
    date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
    date(2025, 10, 4), date(2025, 10, 5), date(2025, 10, 6),
    date(2025, 10, 7), date(2025, 10, 8),
}

CHINA_HOLIDAYS_2026 = {
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 21),
    date(2026, 2, 22),
    date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6),
    date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3),
    date(2026, 5, 4), date(2026, 5, 5),
    date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21),
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
    date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6),
    date(2026, 10, 7),
}

ALL_HOLIDAYS = CHINA_HOLIDAYS_2024 | CHINA_HOLIDAYS_2025 | CHINA_HOLIDAYS_2026


class TradingSession:
    def __init__(self, holidays: Optional[set[date]] = None):
        self._holidays = holidays if holidays is not None else ALL_HOLIDAYS

    def is_trading_day(self, d: Optional[date] = None) -> bool:
        if d is None:
            d = date.today()
        if d.weekday() >= 5:
            return False
        if d in self._holidays:
            return False
        return True

    def is_trading_time(self, dt: Optional[datetime] = None) -> bool:
        if dt is None:
            dt = datetime.now()
        if not self.is_trading_day(dt.date()):
            return False
        t = dt.time()
        if MORNING_OPEN <= t <= MORNING_CLOSE:
            return True
        if AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE:
            return True
        return False

    def get_next_trading_day(self, d: Optional[date] = None) -> date:
        if d is None:
            d = date.today()
        candidate = d + timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate += timedelta(days=1)
            if (candidate - d).days > 30:
                logger.warning("Could not find next trading day within 30 days")
                break
        return candidate

    def get_trading_sessions_today(self, d: Optional[date] = None) -> list[tuple[time, time]]:
        if d is None:
            d = date.today()
        if not self.is_trading_day(d):
            return []
        return [(MORNING_OPEN, MORNING_CLOSE), (AFTERNOON_OPEN, AFTERNOON_CLOSE)]

    def time_to_next_session(self, dt: Optional[datetime] = None) -> Optional[timedelta]:
        if dt is None:
            dt = datetime.now()
        if self.is_trading_time(dt):
            return timedelta(0)
        t = dt.time()
        if self.is_trading_day(dt.date()):
            if t < MORNING_OPEN:
                next_open = datetime.combine(dt.date(), MORNING_OPEN)
                return next_open - dt
            if MORNING_CLOSE < t < AFTERNOON_OPEN:
                next_open = datetime.combine(dt.date(), AFTERNOON_OPEN)
                return next_open - dt
            if t > AFTERNOON_CLOSE:
                next_day = self.get_next_trading_day(dt.date())
                next_open = datetime.combine(next_day, MORNING_OPEN)
                return next_open - dt
        next_day = self.get_next_trading_day(dt.date())
        next_open = datetime.combine(next_day, MORNING_OPEN)
        return next_open - dt

    def add_holidays(self, dates: set[date]) -> None:
        self._holidays = self._holidays | dates

    def remove_holidays(self, dates: set[date]) -> None:
        self._holidays = self._holidays - dates
