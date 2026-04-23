import logging
from typing import Optional

from trading_system.core.events import Event, EventBus, EventType
from trading_system.notification.channels import (
    DingTalkChannel,
    FeishuChannel,
    LogChannel,
    NotificationChannel,
    NotificationLevel,
    NotificationMessage,
    WeChatChannel,
)

logger = logging.getLogger(__name__)


class NotificationManager:
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        feishu_webhook: str = "",
        dingtalk_webhook: str = "",
        dingtalk_secret: str = "",
        wechat_sckey: str = "",
    ):
        self._channels: list[NotificationChannel] = [LogChannel()]

        if feishu_webhook:
            self._channels.append(FeishuChannel(feishu_webhook))
        if dingtalk_webhook:
            self._channels.append(DingTalkChannel(dingtalk_webhook, dingtalk_secret))
        if wechat_sckey:
            self._channels.append(WeChatChannel(wechat_sckey))

        self._event_bus = event_bus
        if event_bus:
            self._subscribe_events()

    def _subscribe_events(self) -> None:
        if not self._event_bus:
            return
        self._event_bus.subscribe(EventType.CIRCUIT_BREAKER, self._on_circuit_breaker)
        self._event_bus.subscribe(EventType.DRAWDOWN_WARNING, self._on_drawdown_warning)
        self._event_bus.subscribe(EventType.ORDER_REJECTED, self._on_order_rejected)
        self._event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
        self._event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)
        self._event_bus.subscribe(EventType.SYSTEM_ERROR, self._on_system_error)

    def _on_circuit_breaker(self, event: Event) -> None:
        self.notify(
            NotificationMessage(
                title="熔断机制触发",
                content=f"交易系统已触发熔断机制，所有交易暂停。\n详情: {event.data}",
                level=NotificationLevel.CRITICAL,
                source="风控系统",
                metadata=event.data
                if isinstance(event.data, dict)
                else {"detail": str(event.data)},
            )
        )

    def _on_drawdown_warning(self, event: Event) -> None:
        self.notify(
            NotificationMessage(
                title="回撤预警",
                content=f"组合回撤已达到预警水平。\n详情: {event.data}",
                level=NotificationLevel.WARNING,
                source="风控系统",
                metadata=event.data
                if isinstance(event.data, dict)
                else {"detail": str(event.data)},
            )
        )

    def _on_order_rejected(self, event: Event) -> None:
        self.notify(
            NotificationMessage(
                title="订单被拒绝",
                content=f"交易信号被风控拒绝。\n详情: {event.data}",
                level=NotificationLevel.WARNING,
                source="交易引擎",
                metadata=event.data
                if isinstance(event.data, dict)
                else {"detail": str(event.data)},
            )
        )

    def _on_order_filled(self, event: Event) -> None:
        self.notify(
            NotificationMessage(
                title="订单成交",
                content=f"交易订单已成交。\n详情: {event.data}",
                level=NotificationLevel.INFO,
                source="交易引擎",
                metadata=event.data
                if isinstance(event.data, dict)
                else {"detail": str(event.data)},
            )
        )

    def _on_position_closed(self, event: Event) -> None:
        self.notify(
            NotificationMessage(
                title="持仓平仓",
                content=f"持仓已平仓。\n详情: {event.data}",
                level=NotificationLevel.INFO,
                source="交易引擎",
                metadata=event.data
                if isinstance(event.data, dict)
                else {"detail": str(event.data)},
            )
        )

    def _on_system_error(self, event: Event) -> None:
        self.notify(
            NotificationMessage(
                title="系统错误",
                content=f"交易系统发生错误。\n详情: {event.data}",
                level=NotificationLevel.CRITICAL,
                source="系统",
                metadata=event.data
                if isinstance(event.data, dict)
                else {"detail": str(event.data)},
            )
        )

    def notify(self, message: NotificationMessage) -> list[bool]:
        results = []
        for channel in self._channels:
            try:
                result = channel.send_sync(message)
                results.append(result)
            except Exception as e:
                logger.error("Notification channel %s failed: %s", type(channel).__name__, e)
                results.append(False)
        return results

    async def notify_async(self, message: NotificationMessage) -> list[bool]:
        results = []
        for channel in self._channels:
            try:
                result = await channel.send(message)
                results.append(result)
            except Exception as e:
                logger.error("Notification channel %s failed: %s", type(channel).__name__, e)
                results.append(False)
        return results

    def add_channel(self, channel: NotificationChannel) -> None:
        self._channels.append(channel)

    @property
    def channel_count(self) -> int:
        return len(self._channels)
