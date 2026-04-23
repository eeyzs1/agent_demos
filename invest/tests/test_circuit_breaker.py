from datetime import datetime, timedelta

import pytest

from trading_system.risk.circuit_breaker import (
    BreakerConfig,
    BreakerStatus,
    BreakerType,
    CircuitBreaker,
)


@pytest.fixture
def breaker():
    cb = CircuitBreaker(BreakerConfig())
    cb.initialize(100000.0)
    return cb


class TestCircuitBreakerDailyLoss:
    def test_no_trigger_below_threshold(self, breaker):
        breaker.update_daily_loss(-2000.0)
        assert not breaker.check_daily_loss()
        assert not breaker.is_any_active

    def test_trigger_at_threshold(self, breaker):
        breaker.update_daily_loss(-3000.0)
        assert breaker.check_daily_loss()
        assert BreakerType.DAILY_LOSS in breaker.active_breakers

    def test_trigger_above_threshold(self, breaker):
        breaker.update_daily_loss(-5000.0)
        assert breaker.check_daily_loss()
        assert not breaker.can_open_position()

    def test_daily_reset(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        assert BreakerType.DAILY_LOSS in breaker.active_breakers
        breaker.reset_daily()
        assert BreakerType.DAILY_LOSS not in breaker.active_breakers


class TestCircuitBreakerTotalDrawdown:
    def test_no_trigger_below_threshold(self, breaker):
        breaker.update_equity(92000.0)
        assert not breaker.check_total_drawdown()

    def test_trigger_at_threshold(self, breaker):
        breaker.update_equity(89000.0)
        assert breaker.check_total_drawdown()
        assert BreakerType.TOTAL_DRAWDOWN in breaker.active_breakers

    def test_total_drawdown_stops_all_trading(self, breaker):
        breaker.update_equity(85000.0)
        breaker.check_total_drawdown()
        assert not breaker.can_trade_at_all()
        assert not breaker.can_open_position()


class TestCircuitBreakerOrderFrequency:
    def test_no_trigger_below_limit(self, breaker):
        for _ in range(4):
            breaker.record_order()
        assert not breaker.check_order_frequency()

    def test_trigger_above_limit(self, breaker):
        for _ in range(6):
            breaker.record_order()
        assert breaker.check_order_frequency()
        assert BreakerType.ORDER_FREQUENCY in breaker.active_breakers

    def test_frequency_window_expiry(self, breaker):
        old_time = datetime.now() - timedelta(seconds=120)
        breaker._order_timestamps = [old_time] * 6
        assert not breaker.check_order_frequency()


class TestCircuitBreakerConcentration:
    def test_no_trigger_below_threshold(self, breaker):
        assert not breaker.check_concentration(25000.0, 100000.0)

    def test_trigger_at_threshold(self, breaker):
        assert breaker.check_concentration(31000.0, 100000.0)
        assert BreakerType.CONCENTRATION in breaker.active_breakers

    def test_cannot_buy_over_concentration(self, breaker):
        breaker.check_concentration(31000.0, 100000.0)
        assert not breaker.can_buy_symbol(31000.0, 100000.0)


class TestCircuitBreakerReset:
    def test_reset_requires_confirmation(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        result = breaker.reset(BreakerType.DAILY_LOSS, confirm=False)
        assert not result
        assert BreakerType.DAILY_LOSS in breaker.active_breakers

    def test_reset_with_confirmation(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        result = breaker.reset(BreakerType.DAILY_LOSS, confirm=True)
        assert result
        assert BreakerType.DAILY_LOSS not in breaker.active_breakers

    def test_reset_all_requires_confirmation(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        result = breaker.reset_all(confirm=False)
        assert not result

    def test_reset_all_with_confirmation(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        breaker.update_equity(85000.0)
        breaker.check_total_drawdown()
        result = breaker.reset_all(confirm=True)
        assert result
        assert not breaker.is_any_active


class TestCircuitBreakerCheckAll:
    def test_check_all_no_trigger(self, breaker):
        breaker.update_equity(98000.0)
        breaker.update_daily_loss(-1000.0)
        assert not breaker.check_all()

    def test_check_all_triggers_daily_loss(self, breaker):
        breaker.update_daily_loss(-4000.0)
        assert breaker.check_all()

    def test_check_all_triggers_drawdown(self, breaker):
        breaker.update_equity(85000.0)
        assert breaker.check_all(symbol_value=0, total_equity=breaker._current_equity)


class TestCircuitBreakerStatus:
    def test_get_status(self, breaker):
        status = breaker.get_status()
        assert "is_any_active" in status
        assert "active_breakers" in status
        assert "breakers" in status
        assert not status["is_any_active"]

    def test_status_after_trigger(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        status = breaker.get_status()
        assert status["is_any_active"]
        assert "daily_loss" in status["active_breakers"]


class TestCircuitBreakerEvents:
    def test_event_recorded_on_trigger(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        events = breaker.events
        assert len(events) >= 1
        assert events[0].breaker_type == BreakerType.DAILY_LOSS
        assert events[0].status == BreakerStatus.ACTIVE

    def test_event_contains_details(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        event = breaker.events[-1]
        assert event.value > 0
        assert event.threshold == 0.03
        assert "单日亏损" in event.message


class TestCircuitBreakerCanTrade:
    def test_can_open_position_when_no_breaker(self, breaker):
        assert breaker.can_open_position()

    def test_cannot_open_when_daily_loss(self, breaker):
        breaker.update_daily_loss(-5000.0)
        breaker.check_daily_loss()
        assert not breaker.can_open_position()

    def test_cannot_open_when_frequency(self, breaker):
        for _ in range(6):
            breaker.record_order()
        breaker.check_order_frequency()
        assert not breaker.can_open_position()

    def test_can_buy_symbol_normal(self, breaker):
        assert breaker.can_buy_symbol(10000.0, 100000.0)

    def test_cannot_buy_symbol_over_concentration(self, breaker):
        assert not breaker.can_buy_symbol(35000.0, 100000.0)
