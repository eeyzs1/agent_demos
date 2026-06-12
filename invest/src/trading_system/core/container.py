import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ServiceContainer:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._singletons: dict[str, Any] = {}

    def register_instance(self, name: str, instance: Any) -> None:
        self._services[name] = instance

    def register_factory(
        self, name: str, factory: Callable[[], Any], singleton: bool = True
    ) -> None:
        self._factories[name] = factory
        if singleton:
            self._singletons.pop(name, None)

    def get(self, name: str) -> Any:
        if name in self._services:
            return self._services[name]
        if name in self._factories:
            if name in self._singletons:
                return self._singletons[name]
            instance = self._factories[name]()
            self._singletons[name] = instance
            return instance
        raise KeyError(f"Service '{name}' not registered")

    def has(self, name: str) -> bool:
        return name in self._services or name in self._factories

    def remove(self, name: str) -> None:
        self._services.pop(name, None)
        self._factories.pop(name, None)
        self._singletons.pop(name, None)

    def list_services(self) -> list[str]:
        names = set(self._services.keys()) | set(self._factories.keys())
        return sorted(names)

    def reset(self) -> None:
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()


def create_container(config: Any) -> ServiceContainer:
    from trading_system.core.config import AppConfig
    from trading_system.core.events import EventBus
    from trading_system.data.store import DataStore
    from trading_system.execution.broker import PaperBroker
    from trading_system.notification.manager import NotificationManager
    from trading_system.risk.manager import RiskManager

    app_config: AppConfig = config

    container = ServiceContainer()

    event_bus = EventBus()
    container.register_instance("event_bus", event_bus)
    container.register_instance("config", app_config)

    container.register_factory(
        "data_store",
        lambda: DataStore(
            cache_dir=app_config.data.cache_dir,
            db_url=app_config.data.database_url,
        ),
        singleton=True,
    )

    container.register_factory(
        "risk_manager",
        lambda: RiskManager(app_config.risk, app_config.trading.initial_capital),
        singleton=True,
    )

    container.register_factory(
        "broker",
        lambda: PaperBroker(initial_capital=app_config.trading.initial_capital),
        singleton=True,
    )

    container.register_factory(
        "notification_manager",
        lambda: NotificationManager(
            event_bus=event_bus,
            feishu_webhook=app_config.notification.feishu_webhook or "",
            dingtalk_webhook=app_config.notification.dingtalk_webhook or "",
            dingtalk_secret=app_config.notification.dingtalk_secret or "",
            wechat_sckey=app_config.notification.wechat_sckey or "",
        ),
        singleton=True,
    )

    return container
