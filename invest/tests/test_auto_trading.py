from unittest.mock import MagicMock, patch


class TestAutoTradingEngine:
    def _create_mock_engine(self):
        with patch('trading_system.execution.engine.TradingEngine.__init__', return_value=None):
            from trading_system.execution.engine import TradingEngine
            from trading_system.ashare.trading_session import TradingSession
            engine = TradingEngine.__new__(TradingEngine)
            engine._running = False
            engine._strategies = {}
            engine._config = MagicMock()
            engine._config.trading.mode = "paper"
            engine._data_store = MagicMock()
            engine._data_store.fetch_realtime.return_value = {"current_price": 0}
            engine._data_store.fetch_daily.return_value = MagicMock()
            engine._data_store.fetch_daily.return_value.empty = True
            engine._risk_manager = MagicMock()
            engine._risk_manager.check_positions.return_value = []
            engine._audit = MagicMock()
            engine._broker = MagicMock()
            engine._trading_session = MagicMock()
            engine._trading_session.is_trading_time.return_value = True
            engine._trading_session.time_to_next_session.return_value = None
            return engine

    def test_run_loop_with_advisor_flag(self):
        engine = self._create_mock_engine()
        engine._running = True

        def stop_after_one(e):
            e._running = False

        engine.run_loop(
            symbols=["600519"],
            interval_seconds=1,
            enable_advisor=True,
            on_cycle=stop_after_one,
        )

        assert not engine._running

    def test_run_loop_without_advisor(self):
        engine = self._create_mock_engine()
        engine._running = True

        def stop_after_one(e):
            e._running = False

        engine.run_loop(
            symbols=["600519"],
            interval_seconds=1,
            enable_advisor=False,
            on_cycle=stop_after_one,
        )

        assert not engine._running
