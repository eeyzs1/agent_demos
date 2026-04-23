import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ReconcileStatus(Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING_LOCAL = "missing_local"
    MISSING_BROKER = "missing_broker"


class ReconcileSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ReconcileItem:
    symbol: str
    status: ReconcileStatus
    severity: ReconcileSeverity
    local_value: Optional[float] = None
    broker_value: Optional[float] = None
    local_quantity: Optional[float] = None
    broker_quantity: Optional[float] = None
    difference: float = 0.0
    message: str = ""


@dataclass
class ReconcileReport:
    reconciled_at: datetime = field(default_factory=datetime.now)
    items: list[ReconcileItem] = field(default_factory=list)
    position_items: list[ReconcileItem] = field(default_factory=list)
    fund_items: list[ReconcileItem] = field(default_factory=list)

    @property
    def is_all_match(self) -> bool:
        return all(
            item.status == ReconcileStatus.MATCH
            for item in self.items
        )

    @property
    def mismatch_count(self) -> int:
        return sum(1 for i in self.items if i.status != ReconcileStatus.MATCH)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.items if i.severity == ReconcileSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.items if i.severity == ReconcileSeverity.WARNING)

    def to_dict(self) -> dict:
        return {
            "reconciled_at": self.reconciled_at.isoformat(),
            "is_all_match": self.is_all_match,
            "mismatch_count": self.mismatch_count,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "items": [
                {
                    "symbol": item.symbol,
                    "status": item.status.value,
                    "severity": item.severity.value,
                    "local_value": item.local_value,
                    "broker_value": item.broker_value,
                    "local_quantity": item.local_quantity,
                    "broker_quantity": item.broker_quantity,
                    "difference": item.difference,
                    "message": item.message,
                }
                for item in self.items
            ],
        }


class Reconciler:
    def __init__(self, notification_manager=None, quantity_tolerance: float = 0.01, value_tolerance: float = 0.02):
        self._notification = notification_manager
        self._quantity_tolerance = quantity_tolerance
        self._value_tolerance = value_tolerance
        self._reports: list[ReconcileReport] = []

    @property
    def reports(self) -> list[ReconcileReport]:
        return list(self._reports)

    def reconcile_positions(
        self,
        local_positions: dict,
        broker_positions: dict,
    ) -> list[ReconcileItem]:
        items = []
        all_symbols = set(local_positions.keys()) | set(broker_positions.keys())

        for symbol in all_symbols:
            local = local_positions.get(symbol)
            broker = broker_positions.get(symbol)

            if local is None and broker is not None:
                items.append(ReconcileItem(
                    symbol=symbol,
                    status=ReconcileStatus.MISSING_LOCAL,
                    severity=ReconcileSeverity.CRITICAL,
                    broker_quantity=broker.get("quantity"),
                    broker_value=broker.get("market_value", broker.get("value")),
                    message=f"本地缺失持仓 {symbol}，券商有 {broker.get('quantity', 0)} 股",
                ))
            elif local is not None and broker is None:
                items.append(ReconcileItem(
                    symbol=symbol,
                    status=ReconcileStatus.MISSING_BROKER,
                    severity=ReconcileSeverity.CRITICAL,
                    local_quantity=local.get("quantity"),
                    local_value=local.get("market_value", local.get("value")),
                    message=f"券商缺失持仓 {symbol}，本地有 {local.get('quantity', 0)} 股",
                ))
            else:
                local_qty = local.get("quantity", 0)
                broker_qty = broker.get("quantity", 0)
                qty_diff = abs(local_qty - broker_qty)

                local_val = local.get("market_value", local.get("value", 0))
                broker_val = broker.get("market_value", broker.get("value", 0))
                val_diff_pct = abs(local_val - broker_val) / max(local_val, broker_val, 1)

                if qty_diff <= self._quantity_tolerance and val_diff_pct <= self._value_tolerance:
                    items.append(ReconcileItem(
                        symbol=symbol,
                        status=ReconcileStatus.MATCH,
                        severity=ReconcileSeverity.INFO,
                        local_quantity=local_qty,
                        broker_quantity=broker_qty,
                        local_value=local_val,
                        broker_value=broker_val,
                        message=f"{symbol} 持仓一致",
                    ))
                else:
                    items.append(ReconcileItem(
                        symbol=symbol,
                        status=ReconcileStatus.MISMATCH,
                        severity=ReconcileSeverity.WARNING,
                        local_quantity=local_qty,
                        broker_quantity=broker_qty,
                        local_value=local_val,
                        broker_value=broker_val,
                        difference=val_diff_pct,
                        message=f"{symbol} 持仓不一致：本地 {local_qty}股/{local_val:.2f} vs 券商 {broker_qty}股/{broker_val:.2f}",
                    ))

        return items

    def reconcile_funds(
        self,
        local_account: dict,
        broker_account: dict,
    ) -> list[ReconcileItem]:
        items = []
        fields = [
            ("cash", "可用资金"),
            ("total_equity", "总资产"),
        ]

        for field_name, display_name in fields:
            local_val = local_account.get(field_name, 0)
            broker_val = broker_account.get(field_name, 0)
            diff_pct = abs(local_val - broker_val) / max(abs(local_val), abs(broker_val), 1)

            if diff_pct <= self._value_tolerance:
                items.append(ReconcileItem(
                    symbol=field_name,
                    status=ReconcileStatus.MATCH,
                    severity=ReconcileSeverity.INFO,
                    local_value=local_val,
                    broker_value=broker_val,
                    message=f"{display_name}一致: {local_val:.2f}",
                ))
            else:
                items.append(ReconcileItem(
                    symbol=field_name,
                    status=ReconcileStatus.MISMATCH,
                    severity=ReconcileSeverity.WARNING,
                    local_value=local_val,
                    broker_value=broker_val,
                    difference=diff_pct,
                    message=f"{display_name}不一致：本地 {local_val:.2f} vs 券商 {broker_val:.2f}",
                ))

        return items

    def reconcile(
        self,
        local_positions: dict,
        broker_positions: dict,
        local_account: dict,
        broker_account: dict,
    ) -> ReconcileReport:
        report = ReconcileReport()

        position_items = self.reconcile_positions(local_positions, broker_positions)
        fund_items = self.reconcile_funds(local_account, broker_account)

        report.position_items = position_items
        report.fund_items = fund_items
        report.items = position_items + fund_items

        self._reports.append(report)

        if report.critical_count > 0 or report.mismatch_count > 0:
            logger.warning(
                "Reconciliation found %d mismatches, %d critical",
                report.mismatch_count,
                report.critical_count,
            )
            self._notify_mismatch(report)
        else:
            logger.info("Reconciliation passed: all positions and funds match")

        return report

    def _notify_mismatch(self, report: ReconcileReport) -> None:
        if not self._notification:
            return
        from trading_system.notification.channels import NotificationLevel, NotificationMessage
        critical_items = [i for i in report.items if i.severity == ReconcileSeverity.CRITICAL]
        warning_items = [i for i in report.items if i.severity == ReconcileSeverity.WARNING]
        content = f"对账发现异常\n严重: {len(critical_items)}项\n警告: {len(warning_items)}项\n"
        for item in critical_items[:5]:
            content += f"\n[严重] {item.message}"
        for item in warning_items[:5]:
            content += f"\n[警告] {item.message}"
        self._notification.notify(
            NotificationMessage(
                title="交易对账异常",
                content=content,
                level=NotificationLevel.WARNING if not critical_items else NotificationLevel.CRITICAL,
                source="对账系统",
            )
        )
