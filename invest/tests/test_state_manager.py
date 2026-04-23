from pathlib import Path

import pytest

from trading_system.execution.state_manager import StateManager


@pytest.fixture
def state_dir(tmp_path):
    return str(tmp_path / "state")


@pytest.fixture
def manager(state_dir):
    return StateManager(state_dir=state_dir)


class TestStateManagerPositions:
    def test_save_and_load_positions(self, manager):
        positions = {
            "600000": {
                "symbol": "600000",
                "side": "long",
                "quantity": 100,
                "entry_price": 10.5,
                "stop_loss": 9.9,
                "take_profit": 12.0,
            }
        }
        manager.save_positions(positions)
        loaded = manager.load_positions()
        assert loaded is not None
        assert "600000" in loaded
        assert loaded["600000"]["quantity"] == 100

    def test_load_positions_no_file(self, manager):
        result = manager.load_positions()
        assert result is None

    def test_save_empty_positions(self, manager):
        manager.save_positions({})
        loaded = manager.load_positions()
        assert loaded == {}


class TestStateManagerDailyTrades:
    def test_save_and_load_trades(self, manager):
        trades = [
            {"symbol": "600000", "side": "buy", "price": 10.5, "quantity": 100},
            {"symbol": "000001", "side": "sell", "price": 15.0, "quantity": 200},
        ]
        manager.save_daily_trades(trades)
        loaded = manager.load_daily_trades()
        assert len(loaded) == 2
        assert loaded[0]["symbol"] == "600000"

    def test_load_trades_no_file(self, manager):
        result = manager.load_daily_trades()
        assert result == []


class TestStateManagerAccount:
    def test_save_and_load_account(self, manager):
        account = {"cash": 50000.0, "total_equity": 100000.0}
        manager.save_account(account)
        loaded = manager.load_account()
        assert loaded is not None
        assert loaded["cash"] == 50000.0

    def test_load_account_no_file(self, manager):
        result = manager.load_account()
        assert result is None


class TestStateManagerFullState:
    def test_save_and_load_full_state(self, manager):
        positions = {"600000": {"quantity": 100}}
        trades = [{"symbol": "600000", "side": "buy"}]
        account = {"cash": 50000.0}
        manager.save_full_state(positions, trades, account)
        state = manager.load_full_state()
        assert "600000" in state["positions"]
        assert len(state["trades"]) == 1
        assert state["account"]["cash"] == 50000.0


class TestStateManagerCorruption:
    def test_detect_corrupted_file(self, manager, state_dir):
        positions_file = Path(state_dir) / "positions.json"
        with open(positions_file, "w") as f:
            f.write("{invalid json content")
        assert manager.is_state_corrupted(positions_file)

    def test_valid_file_not_corrupted(self, manager):
        manager.save_positions({"600000": {"quantity": 100}})
        assert not manager.is_state_corrupted()

    def test_nonexistent_file_not_corrupted(self, manager):
        assert not manager.is_state_corrupted(Path("nonexistent.json"))


class TestStateManagerBackup:
    def test_backup_created_on_full_save(self, manager):
        manager.save_full_state({}, [], {"cash": 100000.0})
        backup_dir = manager._backup_dir
        backups = list(backup_dir.glob("state_*.json"))
        assert len(backups) >= 1

    def test_recover_from_backup(self, manager):
        positions = {"600000": {"quantity": 100}}
        manager.save_full_state(positions, [], {"cash": 50000.0})
        recovered = manager.recover_from_backup()
        assert recovered is not None
        assert "600000" in recovered["positions"]

    def test_no_backup_returns_none(self, manager):
        result = manager.recover_from_backup()
        assert result is None

    def test_backup_rotation(self, manager):
        for i in range(12):
            manager.save_full_state({"sym": {"i": i}}, [], {"cash": float(i)})
        backups = list(manager._backup_dir.glob("state_*.json"))
        assert len(backups) <= 10


class TestStateManagerClear:
    def test_clear_state(self, manager):
        manager.save_positions({"600000": {"quantity": 100}})
        manager.save_daily_trades([{"symbol": "600000"}])
        manager.save_account({"cash": 50000.0})
        manager.clear_state()
        assert manager.load_positions() is None
        assert manager.load_daily_trades() == []
        assert manager.load_account() is None


class TestStateManagerAtomicWrite:
    def test_write_creates_file(self, manager, state_dir):
        manager.save_positions({"test": {"val": 1}})
        assert (Path(state_dir) / "positions.json").exists()

    def test_corrupted_falls_back_to_bak(self, manager, state_dir):
        manager.save_positions({"test": {"val": 1}})
        manager.save_positions({"test": {"val": 2}})
        positions_file = Path(state_dir) / "positions.json"
        with open(positions_file, "w") as f:
            f.write("broken json{{{")
        result = manager.load_positions()
        assert result is not None
