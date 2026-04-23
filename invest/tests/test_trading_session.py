from datetime import date, datetime, timedelta

import pytest

from trading_system.ashare.trading_session import (
    AFTERNOON_CLOSE,
    AFTERNOON_OPEN,
    MORNING_CLOSE,
    MORNING_OPEN,
    TradingSession,
)


@pytest.fixture
def session():
    holidays = {
        date(2024, 1, 1),
        date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3),
    }
    return TradingSession(holidays=holidays)


class TestTradingSessionIsTradingDay:
    def test_weekday_is_trading_day(self, session):
        assert session.is_trading_day(date(2024, 1, 2))

    def test_saturday_not_trading_day(self, session):
        assert not session.is_trading_day(date(2024, 1, 6))

    def test_sunday_not_trading_day(self, session):
        assert not session.is_trading_day(date(2024, 1, 7))

    def test_holiday_not_trading_day(self, session):
        assert not session.is_trading_day(date(2024, 1, 1))

    def test_national_day_holiday(self, session):
        assert not session.is_trading_day(date(2024, 10, 1))
        assert not session.is_trading_day(date(2024, 10, 2))

    def test_regular_workday(self, session):
        assert session.is_trading_day(date(2024, 1, 2))


class TestTradingSessionIsTradingTime:
    def test_morning_session(self, session):
        dt = datetime(2024, 1, 2, 10, 0, 0)
        assert session.is_trading_time(dt)

    def test_afternoon_session(self, session):
        dt = datetime(2024, 1, 2, 14, 0, 0)
        assert session.is_trading_time(dt)

    def test_morning_open_exact(self, session):
        dt = datetime(2024, 1, 2, 9, 30, 0)
        assert session.is_trading_time(dt)

    def test_afternoon_close_exact(self, session):
        dt = datetime(2024, 1, 2, 15, 0, 0)
        assert session.is_trading_time(dt)

    def test_before_open_not_trading(self, session):
        dt = datetime(2024, 1, 2, 9, 0, 0)
        assert not session.is_trading_time(dt)

    def test_lunch_break_not_trading(self, session):
        dt = datetime(2024, 1, 2, 12, 0, 0)
        assert not session.is_trading_time(dt)

    def test_after_close_not_trading(self, session):
        dt = datetime(2024, 1, 2, 16, 0, 0)
        assert not session.is_trading_time(dt)

    def test_weekend_not_trading(self, session):
        dt = datetime(2024, 1, 6, 10, 0, 0)
        assert not session.is_trading_time(dt)

    def test_holiday_not_trading(self, session):
        dt = datetime(2024, 1, 1, 10, 0, 0)
        assert not session.is_trading_time(dt)

    def test_morning_close_boundary(self, session):
        dt = datetime(2024, 1, 2, 11, 30, 0)
        assert session.is_trading_time(dt)

    def test_afternoon_open_boundary(self, session):
        dt = datetime(2024, 1, 2, 13, 0, 0)
        assert session.is_trading_time(dt)


class TestTradingSessionNextTradingDay:
    def test_next_day_is_trading_day(self, session):
        result = session.get_next_trading_day(date(2024, 1, 2))
        assert result == date(2024, 1, 3)

    def test_friday_to_monday(self, session):
        result = session.get_next_trading_day(date(2024, 1, 5))
        assert result == date(2024, 1, 8)

    def test_before_holiday(self, session):
        result = session.get_next_trading_day(date(2023, 12, 31))
        assert result == date(2024, 1, 2)


class TestTradingSessionSessionsToday:
    def test_trading_day_has_two_sessions(self, session):
        sessions = session.get_trading_sessions_today(date(2024, 1, 2))
        assert len(sessions) == 2
        assert sessions[0] == (MORNING_OPEN, MORNING_CLOSE)
        assert sessions[1] == (AFTERNOON_OPEN, AFTERNOON_CLOSE)

    def test_non_trading_day_no_sessions(self, session):
        sessions = session.get_trading_sessions_today(date(2024, 1, 6))
        assert sessions == []

    def test_holiday_no_sessions(self, session):
        sessions = session.get_trading_sessions_today(date(2024, 1, 1))
        assert sessions == []


class TestTradingSessionTimeToNext:
    def test_during_trading_time(self, session):
        dt = datetime(2024, 1, 2, 10, 0, 0)
        result = session.time_to_next_session(dt)
        assert result == timedelta(0)

    def test_before_morning_open(self, session):
        dt = datetime(2024, 1, 2, 8, 0, 0)
        result = session.time_to_next_session(dt)
        assert result is not None
        assert result.total_seconds() > 0

    def test_lunch_break(self, session):
        dt = datetime(2024, 1, 2, 12, 0, 0)
        result = session.time_to_next_session(dt)
        assert result is not None
        assert result.total_seconds() > 0

    def test_after_close(self, session):
        dt = datetime(2024, 1, 2, 16, 0, 0)
        result = session.time_to_next_session(dt)
        assert result is not None
        assert result.total_seconds() > 0


class TestTradingSessionHolidays:
    def test_add_holidays(self, session):
        new_holiday = date(2024, 3, 15)
        assert session.is_trading_day(new_holiday)
        session.add_holidays({new_holiday})
        assert not session.is_trading_day(new_holiday)

    def test_remove_holidays(self, session):
        holiday = date(2024, 1, 1)
        assert not session.is_trading_day(holiday)
        session.remove_holidays({holiday})
        assert session.is_trading_day(holiday)


class TestTradingEngineSessionProtection:
    def test_trading_engine_has_session(self):
        from trading_system.ashare.trading_session import TradingSession
        session = TradingSession()
        assert session is not None
        assert hasattr(session, 'is_trading_time')
        assert hasattr(session, 'is_trading_day')

    def test_session_is_trading_time_method(self):
        session = TradingSession()
        dt = datetime(2024, 1, 2, 10, 0, 0)
        assert session.is_trading_time(dt)
