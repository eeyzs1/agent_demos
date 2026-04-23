import pytest

from trading_system.execution.reconciler import (
    ReconcileItem,
    Reconciler,
    ReconcileReport,
    ReconcileSeverity,
    ReconcileStatus,
)


@pytest.fixture
def reconciler():
    return Reconciler()


class TestReconcilePositions:
    def test_matching_positions(self, reconciler):
        local = {"600000": {"quantity": 100, "market_value": 1050.0}}
        broker = {"600000": {"quantity": 100, "market_value": 1050.0}}
        items = reconciler.reconcile_positions(local, broker)
        assert len(items) == 1
        assert items[0].status == ReconcileStatus.MATCH

    def test_missing_local(self, reconciler):
        local = {}
        broker = {"600000": {"quantity": 100, "market_value": 1050.0}}
        items = reconciler.reconcile_positions(local, broker)
        assert len(items) == 1
        assert items[0].status == ReconcileStatus.MISSING_LOCAL
        assert items[0].severity == ReconcileSeverity.CRITICAL

    def test_missing_broker(self, reconciler):
        local = {"600000": {"quantity": 100, "market_value": 1050.0}}
        broker = {}
        items = reconciler.reconcile_positions(local, broker)
        assert len(items) == 1
        assert items[0].status == ReconcileStatus.MISSING_BROKER
        assert items[0].severity == ReconcileSeverity.CRITICAL

    def test_quantity_mismatch(self, reconciler):
        local = {"600000": {"quantity": 100, "market_value": 1050.0}}
        broker = {"600000": {"quantity": 200, "market_value": 2100.0}}
        items = reconciler.reconcile_positions(local, broker)
        assert len(items) == 1
        assert items[0].status == ReconcileStatus.MISMATCH

    def test_multiple_symbols(self, reconciler):
        local = {
            "600000": {"quantity": 100, "market_value": 1050.0},
            "000001": {"quantity": 200, "market_value": 3000.0},
        }
        broker = {
            "600000": {"quantity": 100, "market_value": 1050.0},
            "000001": {"quantity": 200, "market_value": 3000.0},
        }
        items = reconciler.reconcile_positions(local, broker)
        assert len(items) == 2
        assert all(i.status == ReconcileStatus.MATCH for i in items)

    def test_partial_mismatch(self, reconciler):
        local = {
            "600000": {"quantity": 100, "market_value": 1050.0},
            "000001": {"quantity": 200, "market_value": 3000.0},
        }
        broker = {
            "600000": {"quantity": 100, "market_value": 1050.0},
            "000001": {"quantity": 150, "market_value": 2250.0},
        }
        items = reconciler.reconcile_positions(local, broker)
        match_items = [i for i in items if i.status == ReconcileStatus.MATCH]
        mismatch_items = [i for i in items if i.status == ReconcileStatus.MISMATCH]
        assert len(match_items) == 1
        assert len(mismatch_items) == 1


class TestReconcileFunds:
    def test_matching_funds(self, reconciler):
        local = {"cash": 50000.0, "total_equity": 100000.0}
        broker = {"cash": 50000.0, "total_equity": 100000.0}
        items = reconciler.reconcile_funds(local, broker)
        assert all(i.status == ReconcileStatus.MATCH for i in items)

    def test_cash_mismatch(self, reconciler):
        local = {"cash": 50000.0, "total_equity": 100000.0}
        broker = {"cash": 45000.0, "total_equity": 100000.0}
        items = reconciler.reconcile_funds(local, broker)
        cash_items = [i for i in items if i.symbol == "cash"]
        assert len(cash_items) == 1
        assert cash_items[0].status == ReconcileStatus.MISMATCH

    def test_equity_mismatch(self, reconciler):
        local = {"cash": 50000.0, "total_equity": 100000.0}
        broker = {"cash": 50000.0, "total_equity": 95000.0}
        items = reconciler.reconcile_funds(local, broker)
        equity_items = [i for i in items if i.symbol == "total_equity"]
        assert len(equity_items) == 1
        assert equity_items[0].status == ReconcileStatus.MISMATCH


class TestReconcileFull:
    def test_full_reconcile_match(self, reconciler):
        local_positions = {"600000": {"quantity": 100, "market_value": 1050.0}}
        broker_positions = {"600000": {"quantity": 100, "market_value": 1050.0}}
        local_account = {"cash": 50000.0, "total_equity": 100000.0}
        broker_account = {"cash": 50000.0, "total_equity": 100000.0}
        report = reconciler.reconcile(local_positions, broker_positions, local_account, broker_account)
        assert report.is_all_match
        assert report.mismatch_count == 0

    def test_full_reconcile_mismatch(self, reconciler):
        local_positions = {"600000": {"quantity": 100, "market_value": 1050.0}}
        broker_positions = {"600000": {"quantity": 200, "market_value": 2100.0}}
        local_account = {"cash": 50000.0, "total_equity": 100000.0}
        broker_account = {"cash": 50000.0, "total_equity": 100000.0}
        report = reconciler.reconcile(local_positions, broker_positions, local_account, broker_account)
        assert not report.is_all_match
        assert report.mismatch_count > 0

    def test_report_stored(self, reconciler):
        local_positions = {}
        broker_positions = {}
        local_account = {"cash": 0, "total_equity": 0}
        broker_account = {"cash": 0, "total_equity": 0}
        reconciler.reconcile(local_positions, broker_positions, local_account, broker_account)
        assert len(reconciler.reports) == 1


class TestReconcileReport:
    def test_to_dict(self, reconciler):
        local_positions = {"600000": {"quantity": 100, "market_value": 1050.0}}
        broker_positions = {"600000": {"quantity": 100, "market_value": 1050.0}}
        local_account = {"cash": 50000.0, "total_equity": 100000.0}
        broker_account = {"cash": 50000.0, "total_equity": 100000.0}
        report = reconciler.reconcile(local_positions, broker_positions, local_account, broker_account)
        d = report.to_dict()
        assert "reconciled_at" in d
        assert "is_all_match" in d
        assert "items" in d
        assert d["is_all_match"] is True

    def test_critical_count(self):
        report = ReconcileReport()
        report.items = [
            ReconcileItem(symbol="A", status=ReconcileStatus.MATCH, severity=ReconcileSeverity.INFO, message=""),
            ReconcileItem(symbol="B", status=ReconcileStatus.MISSING_LOCAL, severity=ReconcileSeverity.CRITICAL, message=""),
        ]
        assert report.critical_count == 1
        assert report.mismatch_count == 1

    def test_warning_count(self):
        report = ReconcileReport()
        report.items = [
            ReconcileItem(symbol="A", status=ReconcileStatus.MATCH, severity=ReconcileSeverity.INFO, message=""),
            ReconcileItem(symbol="B", status=ReconcileStatus.MISMATCH, severity=ReconcileSeverity.WARNING, message=""),
        ]
        assert report.warning_count == 1
