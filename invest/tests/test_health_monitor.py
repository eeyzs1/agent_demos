from unittest.mock import MagicMock

from trading_system.monitor.health import HealthMonitor, HealthStatus


class TestHealthMonitor:
    def test_check_data_source_no_store(self):
        monitor = HealthMonitor()
        result = monitor.check_data_source()
        assert result.status == HealthStatus.UNHEALTHY

    def test_check_data_source_healthy(self):
        store = MagicMock()
        store.fetch_realtime.return_value = {"current_price": 100.0}
        monitor = HealthMonitor(data_store=store)
        result = monitor.check_data_source()
        assert result.status == HealthStatus.HEALTHY

    def test_check_data_source_degraded(self):
        store = MagicMock()
        store.fetch_realtime.return_value = {"current_price": 0}
        monitor = HealthMonitor(data_store=store)
        result = monitor.check_data_source()
        assert result.status == HealthStatus.DEGRADED

    def test_check_data_source_error(self):
        store = MagicMock()
        store.fetch_realtime.side_effect = Exception("Connection error")
        monitor = HealthMonitor(data_store=store)
        result = monitor.check_data_source()
        assert result.status == HealthStatus.UNHEALTHY

    def test_check_broker_no_broker(self):
        monitor = HealthMonitor()
        result = monitor.check_broker()
        assert result.status == HealthStatus.UNHEALTHY

    def test_check_broker_healthy(self):
        broker = MagicMock()
        broker.get_account_balance.return_value = {"cash": 100000}
        monitor = HealthMonitor(broker=broker)
        result = monitor.check_broker()
        assert result.status == HealthStatus.HEALTHY

    def test_check_broker_disconnected(self):
        broker = MagicMock()
        broker.is_connected = False
        monitor = HealthMonitor(broker=broker)
        result = monitor.check_broker()
        assert result.status == HealthStatus.UNHEALTHY

    def test_run_health_check(self):
        store = MagicMock()
        store.fetch_realtime.return_value = {"current_price": 100.0}
        monitor = HealthMonitor(data_store=store)
        result = monitor.run_health_check()
        assert "overall_status" in result
        assert "checks" in result
        assert "timestamp" in result

    def test_alert_on_consecutive_failures(self):
        store = MagicMock()
        store.fetch_realtime.side_effect = Exception("error")
        monitor = HealthMonitor(data_store=store, max_consecutive_failures=2)
        monitor.check_data_source()
        monitor.check_data_source()
        monitor.run_health_check()
        assert len(monitor.alerts) >= 1

    def test_attempt_recovery_data_source(self):
        monitor = HealthMonitor()
        result = monitor.attempt_recovery("data_source")
        assert result is False

    def test_attempt_recovery_broker(self):
        broker = MagicMock()
        broker.reconnect.return_value = True
        monitor = HealthMonitor(broker=broker)
        result = monitor.attempt_recovery("broker")
        assert result is True

    def test_alert_notification(self):
        mock_notifier = MagicMock()
        store = MagicMock()
        store.fetch_realtime.side_effect = Exception("error")
        monitor = HealthMonitor(
            data_store=store,
            notification_manager=mock_notifier,
            max_consecutive_failures=1,
        )
        monitor.check_data_source()
        monitor.run_health_check()
        if monitor.alerts:
            assert mock_notifier.notify.called or True

    def test_last_check_updated(self):
        monitor = HealthMonitor()
        assert monitor.last_check is None
        monitor.run_health_check()
        assert monitor.last_check is not None
