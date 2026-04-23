import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict = field(default_factory=dict)


@dataclass
class AlertEvent:
    name: str
    level: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False


class HealthMonitor:
    def __init__(
        self,
        data_store=None,
        broker=None,
        notification_manager=None,
        check_interval: int = 60,
        data_source_timeout: int = 30,
        max_consecutive_failures: int = 3,
    ):
        self._data_store = data_store
        self._broker = broker
        self._notification_manager = notification_manager
        self._check_interval = check_interval
        self._data_source_timeout = data_source_timeout
        self._max_consecutive_failures = max_consecutive_failures
        self._consecutive_failures: dict[str, int] = {}
        self._alerts: list[AlertEvent] = []
        self._last_check: Optional[datetime] = None
        self._running = False

    def check_data_source(self, source: str = "akshare") -> HealthCheckResult:
        start = time.time()
        try:
            if self._data_store is None:
                return HealthCheckResult(
                    name="data_source",
                    status=HealthStatus.UNHEALTHY,
                    message="DataStore not configured",
                )

            rt = self._data_store.fetch_realtime("000001", source=source)
            latency = (time.time() - start) * 1000

            if rt and rt.get("current_price", 0) > 0:
                self._consecutive_failures["data_source"] = 0
                return HealthCheckResult(
                    name="data_source",
                    status=HealthStatus.HEALTHY,
                    message="Data source available",
                    latency_ms=round(latency, 2),
                )
            else:
                self._consecutive_failures["data_source"] = self._consecutive_failures.get("data_source", 0) + 1
                return HealthCheckResult(
                    name="data_source",
                    status=HealthStatus.DEGRADED,
                    message="Data source returned empty data",
                    latency_ms=round(latency, 2),
                )

        except Exception as e:
            self._consecutive_failures["data_source"] = self._consecutive_failures.get("data_source", 0) + 1
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                name="data_source",
                status=HealthStatus.UNHEALTHY,
                message=f"Data source error: {e}",
                latency_ms=round(latency, 2),
            )

    def check_broker(self) -> HealthCheckResult:
        if self._broker is None:
            return HealthCheckResult(
                name="broker",
                status=HealthStatus.UNHEALTHY,
                message="Broker not configured",
            )

        try:
            if hasattr(self._broker, 'is_connected') and not self._broker.is_connected:
                return HealthCheckResult(
                    name="broker",
                    status=HealthStatus.UNHEALTHY,
                    message="Broker disconnected",
                )

            balance = self._broker.get_account_balance()
            if balance:
                return HealthCheckResult(
                    name="broker",
                    status=HealthStatus.HEALTHY,
                    message="Broker connected",
                    details=balance,
                )
            else:
                return HealthCheckResult(
                    name="broker",
                    status=HealthStatus.DEGRADED,
                    message="Broker returned empty balance",
                )

        except Exception as e:
            return HealthCheckResult(
                name="broker",
                status=HealthStatus.UNHEALTHY,
                message=f"Broker error: {e}",
            )

    def check_system_resources(self) -> HealthCheckResult:
        try:
            import psutil
            cpu_pct = psutil.cpu_percent()
            mem_pct = psutil.virtual_memory().percent
            disk_pct = psutil.disk_usage("/").percent

            if cpu_pct > 90 or mem_pct > 90 or disk_pct > 95:
                status = HealthStatus.CRITICAL
            elif cpu_pct > 75 or mem_pct > 80 or disk_pct > 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                name="system_resources",
                status=status,
                message=f"CPU: {cpu_pct}%, MEM: {mem_pct}%, DISK: {disk_pct}%",
                details={"cpu": cpu_pct, "memory": mem_pct, "disk": disk_pct},
            )
        except ImportError:
            return HealthCheckResult(
                name="system_resources",
                status=HealthStatus.HEALTHY,
                message="psutil not available, skipping resource check",
            )

    def run_health_check(self) -> dict:
        results = {
            "data_source": self.check_data_source(),
            "broker": self.check_broker(),
            "system_resources": self.check_system_resources(),
        }

        overall = HealthStatus.HEALTHY
        for result in results.values():
            if result.status == HealthStatus.CRITICAL:
                overall = HealthStatus.CRITICAL
                break
            elif result.status == HealthStatus.UNHEALTHY:
                overall = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall == HealthStatus.HEALTHY:
                overall = HealthStatus.DEGRADED

        self._last_check = datetime.now()
        self._handle_alerts(results, overall)

        return {
            "overall_status": overall,
            "checks": {k: {"status": v.status.value, "message": v.message, "latency_ms": v.latency_ms}
                       for k, v in results.items()},
            "timestamp": self._last_check.isoformat(),
        }

    def _handle_alerts(self, results: dict, overall: HealthStatus) -> None:
        if overall in (HealthStatus.UNHEALTHY, HealthStatus.CRITICAL):
            for name, result in results.items():
                if result.status in (HealthStatus.UNHEALTHY, HealthStatus.CRITICAL):
                    failures = self._consecutive_failures.get(name, 0)
                    if failures >= self._max_consecutive_failures:
                        alert = AlertEvent(
                            name=name,
                            level="critical" if result.status == HealthStatus.CRITICAL else "warning",
                            message=f"{name}: {result.message} (consecutive failures: {failures})",
                        )
                        self._alerts.append(alert)
                        self._send_alert(alert)

    def _send_alert(self, alert: AlertEvent) -> None:
        if self._notification_manager:
            try:
                from trading_system.notification.channels import (
                    NotificationLevel,
                    NotificationMessage,
                )
                level = NotificationLevel.CRITICAL if alert.level == "critical" else NotificationLevel.WARNING
                msg = NotificationMessage(
                    title=f"系统告警: {alert.name}",
                    content=alert.message,
                    level=level,
                    source="健康监控",
                )
                self._notification_manager.notify(msg)
            except Exception as e:
                logger.error("Failed to send alert: %s", e)

    def attempt_recovery(self, component: str) -> bool:
        if component == "data_source":
            try:
                if self._data_store:
                    self._data_store.fetch_realtime("000001", source="yfinance")
                    logger.info("Recovered data source by switching to yfinance")
                    return True
            except Exception:
                return False

        elif component == "broker":
            if hasattr(self._broker, 'reconnect'):
                result = self._broker.reconnect()
                if result:
                    logger.info("Recovered broker connection")
                return result

        return False

    @property
    def alerts(self) -> list[AlertEvent]:
        return list(self._alerts)

    @property
    def last_check(self) -> Optional[datetime]:
        return self._last_check
