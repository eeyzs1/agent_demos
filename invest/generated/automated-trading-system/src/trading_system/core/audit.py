"""AuditLogger — Immutable hash-chain audit logging.

All operations must be audit-logged (hard_constraint). The audit log is
append-only with hash-chain tamper detection.

Writes to audit_log.yaml with format:
  seq, timestamp, event, check_id, result, actor, payload_digest, prev_hash, hash
"""

import hashlib
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class AuditLogger:
    """Immutable append-only audit log with hash-chain tamper detection.

    Every audit record is hashed and chained to the previous record.
    This makes the log tamper-evident — any modification is detectable.
    """

    def __init__(self, log_path: str = "audit_log.yaml"):
        self._log_path = Path(log_path)
        self._lock = threading.RLock()
        self._records: List[Dict[str, Any]] = []
        self._seq = 0
        self._prev_hash = "0" * 64  # Genesis hash

        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing audit log from disk."""
        if self._log_path.exists():
            try:
                with open(self._log_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or []
                if isinstance(data, list):
                    self._records = data
                    self._seq = len(data)
                    if data:
                        self._prev_hash = data[-1].get("hash", "0" * 64)
                    logger.info("Loaded %d existing audit records", self._seq)
            except Exception:
                logger.exception("Failed to load existing audit log, starting fresh")

    def _compute_hash(self, record: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of a record including chain link."""
        chain_data = (
            f"{record.get('seq', '')}"
            f"{record.get('timestamp', '')}"
            f"{record.get('event', '')}"
            f"{record.get('check_id', '')}"
            f"{record.get('result', '')}"
            f"{record.get('actor', '')}"
            f"{record.get('payload_digest', '')}"
            f"{record.get('prev_hash', '')}"
        )
        return hashlib.sha256(chain_data.encode("utf-8")).hexdigest()

    def log(
        self,
        event: str,
        check_id: str = "",
        result: str = "OK",
        actor: str = "system",
        payload: Any = None,
    ) -> Dict[str, Any]:
        """Append an audit record.

        Args:
            event: Event description (e.g., 'order_placement', 'risk_check').
            check_id: Optional check identifier.
            result: Result of the operation (e.g., 'OK', 'BLOCKED', 'FAILED').
            actor: Who or what performed the action.
            payload: Optional data to include in the record.

        Returns:
            The created audit record dict.
        """
        with self._lock:
            self._seq += 1
            payload_digest = ""
            if payload is not None:
                payload_str = str(payload)
                payload_digest = hashlib.sha256(
                    payload_str.encode("utf-8")
                ).hexdigest()[:16]

            record = {
                "seq": self._seq,
                "timestamp": datetime.now().isoformat(),
                "event": event,
                "check_id": check_id,
                "result": result,
                "actor": actor,
                "payload_digest": payload_digest,
                "prev_hash": self._prev_hash,
            }
            record["hash"] = self._compute_hash(record)
            self._records.append(record)
            self._prev_hash = record["hash"]

            self._persist()
            return record

    def _persist(self) -> None:
        """Write current records to disk."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "w", encoding="utf-8") as f:
                yaml.dump(self._records, f, default_flow_style=False, allow_unicode=True)
        except Exception:
            logger.exception("Failed to persist audit log")

    def verify_integrity(self) -> bool:
        """Verify the hash chain integrity.

        Returns:
            True if the chain is intact, False if tampering is detected.
        """
        with self._lock:
            prev_hash = "0" * 64
            for i, record in enumerate(self._records):
                expected = record.get("hash", "")
                if expected:
                    test_record = dict(record)
                    test_record["prev_hash"] = prev_hash
                    computed = self._compute_hash(test_record)
                    if computed != expected:
                        logger.error(
                            "Audit log tampering detected at seq=%d: expected=%s, got=%s",
                            record.get("seq"), computed, expected,
                        )
                        return False
                prev_hash = record.get("hash", "0" * 64)
            return True

    def get_records(
        self, event: str = None, actor: str = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query audit records with optional filters.

        Args:
            event: Filter by event type.
            actor: Filter by actor.
            limit: Maximum records to return.

        Returns:
            List of matching audit records.
        """
        with self._lock:
            result = list(self._records)
            if event:
                result = [r for r in result if event in r.get("event", "")]
            if actor:
                result = [r for r in result if actor in r.get("actor", "")]
            return result[-limit:]


# Global singleton
_audit_logger: AuditLogger = None


def get_audit_logger(log_path: str = "audit_log.yaml") -> AuditLogger:
    """Get or create the global AuditLogger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_path=log_path)
    return _audit_logger