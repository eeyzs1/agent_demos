import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Callable

import httpx

logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if result:
                        return result
                except Exception as e:
                    last_exception = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
            if last_exception:
                logger.error("Retry exhausted: %s failed after %d attempts: %s",
                             func.__name__, max_retries, last_exception)
            return False
        return wrapper
    return decorator


class NotificationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class NotificationMessage:
    title: str
    content: str
    level: NotificationLevel = NotificationLevel.INFO
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    metadata: dict = field(default_factory=dict)

    def to_text(self) -> str:
        level_emoji = {
            NotificationLevel.INFO: "📊",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.CRITICAL: "🚨",
        }
        emoji = level_emoji.get(self.level, "")
        lines = [
            f"{emoji} {self.title}",
            f"时间: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"来源: {self.source or '系统'}",
            "",
            self.content,
        ]
        if self.metadata:
            lines.append("")
            lines.append("详细信息:")
            for k, v in self.metadata.items():
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def to_feishu_card(self) -> dict:
        level_color = {
            NotificationLevel.INFO: "blue",
            NotificationLevel.WARNING: "orange",
            NotificationLevel.CRITICAL: "red",
        }
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": self.title},
                    "template": level_color.get(self.level, "blue"),
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**时间**: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"**来源**: {self.source or '系统'}\n\n"
                                f"{self.content}"
                            ),
                        },
                    },
                ],
            },
        }

    def to_dingtalk_markdown(self) -> dict:
        level_icon = {
            NotificationLevel.INFO: "📊",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.CRITICAL: "🚨",
        }
        icon = level_icon.get(self.level, "")
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"{icon} {self.title}",
                "text": f"### {icon} {self.title}\n\n"
                f"> 时间: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"> 来源: {self.source or '系统'}\n\n"
                f"{self.content}",
            },
        }


class NotificationChannel(ABC):
    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        pass

    @abstractmethod
    def send_sync(self, message: NotificationMessage) -> bool:
        pass


class FeishuChannel(NotificationChannel):
    def __init__(self, webhook_url: str):
        self._webhook_url = webhook_url

    async def send(self, message: NotificationMessage) -> bool:
        try:
            payload = message.to_feishu_card()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._webhook_url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0 or result.get("StatusCode") == 0:
                        logger.info("Feishu notification sent: %s", message.title)
                        return True
                    logger.warning("Feishu API error: %s", result)
                else:
                    logger.warning("Feishu HTTP error: %d", resp.status_code)
        except Exception as e:
            logger.error("Feishu notification failed: %s", e)
        return False

    @retry_on_failure(max_retries=3, base_delay=1.0)
    def send_sync(self, message: NotificationMessage) -> bool:
        try:
            payload = message.to_feishu_card()
            with httpx.Client(timeout=10) as client:
                resp = client.post(self._webhook_url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0 or result.get("StatusCode") == 0:
                        logger.info("Feishu notification sent: %s", message.title)
                        return True
                    logger.warning("Feishu API error: %s", result)
                else:
                    logger.warning("Feishu HTTP error: %d", resp.status_code)
        except Exception as e:
            logger.error("Feishu notification failed: %s", e)
        return False


class DingTalkChannel(NotificationChannel):
    def __init__(self, webhook_url: str, secret: str = ""):
        self._webhook_url = webhook_url
        self._secret = secret

    def _sign_url(self) -> str:
        if not self._secret:
            return self._webhook_url
        import base64
        import hashlib
        import hmac
        import time
        import urllib.parse

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        separator = "&" if "?" in self._webhook_url else "?"
        return f"{self._webhook_url}{separator}timestamp={timestamp}&sign={sign}"

    async def send(self, message: NotificationMessage) -> bool:
        try:
            payload = message.to_dingtalk_markdown()
            url = self._sign_url()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("errcode") == 0:
                        logger.info("DingTalk notification sent: %s", message.title)
                        return True
                    logger.warning("DingTalk API error: %s", result)
                else:
                    logger.warning("DingTalk HTTP error: %d", resp.status_code)
        except Exception as e:
            logger.error("DingTalk notification failed: %s", e)
        return False

    @retry_on_failure(max_retries=3, base_delay=1.0)
    def send_sync(self, message: NotificationMessage) -> bool:
        try:
            payload = message.to_dingtalk_markdown()
            url = self._sign_url()
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("errcode") == 0:
                        logger.info("DingTalk notification sent: %s", message.title)
                        return True
                    logger.warning("DingTalk API error: %s", result)
                else:
                    logger.warning("DingTalk HTTP error: %d", resp.status_code)
        except Exception as e:
            logger.error("DingTalk notification failed: %s", e)
        return False


class WeChatChannel(NotificationChannel):
    def __init__(self, sckey: str):
        self._sckey = sckey
        self._url = f"https://sctapi.ftqq.com/{sckey}.send"

    async def send(self, message: NotificationMessage) -> bool:
        try:
            data = {"title": message.title, "desp": message.content}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url, data=data)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0:
                        logger.info("WeChat notification sent: %s", message.title)
                        return True
                    logger.warning("WeChat API error: %s", result)
                else:
                    logger.warning("WeChat HTTP error: %d", resp.status_code)
        except Exception as e:
            logger.error("WeChat notification failed: %s", e)
        return False

    @retry_on_failure(max_retries=3, base_delay=1.0)
    def send_sync(self, message: NotificationMessage) -> bool:
        try:
            data = {"title": message.title, "desp": message.content}
            with httpx.Client(timeout=10) as client:
                resp = client.post(self._url, data=data)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0:
                        logger.info("WeChat notification sent: %s", message.title)
                        return True
                    logger.warning("WeChat API error: %s", result)
                else:
                    logger.warning("WeChat HTTP error: %d", resp.status_code)
        except Exception as e:
            logger.error("WeChat notification failed: %s", e)
        return False


class LogChannel(NotificationChannel):
    def __init__(self):
        self._logger = logging.getLogger("trading_system.notification")

    async def send(self, message: NotificationMessage) -> bool:
        self._logger.info("[NOTIFICATION] %s", message.to_text())
        return True

    def send_sync(self, message: NotificationMessage) -> bool:
        self._logger.info("[NOTIFICATION] %s", message.to_text())
        return True
