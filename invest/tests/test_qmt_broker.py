from trading_system.execution.broker import Order, OrderSide, OrderStatus, OrderType
from trading_system.execution.qmt_broker import QmtBroker


class TestQmtBroker:
    def test_creation(self):
        broker = QmtBroker(
            qmt_path="/path/to/qmt",
            account_id="123456",
            password="secret",
        )
        assert broker._qmt_path == "/path/to/qmt"
        assert broker._account_id == "123456"
        assert not broker.is_connected

    def test_connect_without_sdk(self):
        broker = QmtBroker()
        result = broker.connect()
        assert result is False
        assert not broker.is_connected

    def test_submit_order_disconnected(self):
        broker = QmtBroker()
        order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=100.0,
        )
        result = broker.submit_order(order)
        assert result.status == OrderStatus.REJECTED

    def test_cancel_order_disconnected(self):
        broker = QmtBroker()
        result = broker.cancel_order("QMT-123")
        assert result is False

    def test_get_positions_disconnected(self):
        broker = QmtBroker()
        result = broker.get_positions()
        assert result == []

    def test_get_account_disconnected(self):
        broker = QmtBroker()
        result = broker.get_account()
        assert result == {}

    def test_reconnect(self):
        broker = QmtBroker()
        result = broker.reconnect()
        assert result is False

    def test_disconnect(self):
        broker = QmtBroker()
        broker.disconnect()
        assert not broker.is_connected

    def test_check_heartbeat_disconnected(self):
        broker = QmtBroker()
        result = broker.check_heartbeat()
        assert result is False
