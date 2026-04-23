import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, log_dir: str = "./logs"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._audit_path = self._log_dir / "audit.jsonl"
        self._trade_path = self._log_dir / "trades.jsonl"
        self._logger = logging.getLogger("audit")

    def log_action(
        self,
        action: str,
        actor: str,
        details: dict[str, Any] | None = None,
        level: str = "INFO",
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "actor": actor,
            "details": details or {},
            "level": level,
        }
        self._write_jsonl(self._audit_path, entry)
        self._logger.log(getattr(logging, level), "%s by %s: %s", action, actor, details)

    def log_trade(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        strategy: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        r_multiple: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "strategy": strategy,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "r_multiple": r_multiple,
            "details": details or {},
        }
        self._write_jsonl(self._trade_path, entry)

    def log_risk_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "details": details or {},
        }
        self._write_jsonl(self._audit_path, entry)
        self._logger.warning("Risk event [%s]: %s - %s", severity, event_type, message)

    def _write_jsonl(self, path: Path, entry: dict) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def read_audit_log(self, limit: int = 100) -> list[dict]:
        return self._read_jsonl(self._audit_path, limit)

    def read_trade_log(self, limit: int = 100) -> list[dict]:
        return self._read_jsonl(self._trade_path, limit)

    def _read_jsonl(self, path: Path, limit: int) -> list[dict]:
        if not path.exists():
            return []
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:]
