import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self, state_dir: str = "./data/state/"):
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._positions_file = self._state_dir / "positions.json"
        self._trades_file = self._state_dir / "daily_trades.json"
        self._account_file = self._state_dir / "account.json"
        self._backup_dir = self._state_dir / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def save_positions(self, positions: dict) -> None:
        data = {
            "saved_at": datetime.now().isoformat(),
            "positions": positions,
        }
        self._write_json(self._positions_file, data)
        logger.debug("Saved %d positions to state file", len(positions))

    def load_positions(self) -> Optional[dict]:
        data = self._read_json(self._positions_file)
        if data is None:
            return None
        return data.get("positions", {})

    def save_daily_trades(self, trades: list) -> None:
        data = {
            "saved_at": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "trades": trades,
        }
        self._write_json(self._trades_file, data)
        logger.debug("Saved %d daily trades to state file", len(trades))

    def load_daily_trades(self) -> list:
        data = self._read_json(self._trades_file)
        if data is None:
            return []
        return data.get("trades", [])

    def save_account(self, account: dict) -> None:
        data = {
            "saved_at": datetime.now().isoformat(),
            "account": account,
        }
        self._write_json(self._account_file, data)

    def load_account(self) -> Optional[dict]:
        data = self._read_json(self._account_file)
        if data is None:
            return None
        return data.get("account")

    def save_full_state(self, positions: dict, trades: list, account: dict) -> None:
        self.save_positions(positions)
        self.save_daily_trades(trades)
        self.save_account(account)
        self._create_backup()

    def load_full_state(self) -> dict:
        return {
            "positions": self.load_positions() or {},
            "trades": self.load_daily_trades(),
            "account": self.load_account() or {},
        }

    def is_state_corrupted(self, filepath: Optional[Path] = None) -> bool:
        target = filepath or self._positions_file
        try:
            data = self._read_json(target)
            return data is None and target.exists()
        except Exception:
            return True

    def recover_from_backup(self) -> Optional[dict]:
        backups = sorted(
            self._backup_dir.glob("state_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for backup in backups:
            try:
                data = self._read_json(backup)
                if data is not None:
                    logger.info("Recovered state from backup: %s", backup.name)
                    return data
            except Exception:
                continue
        logger.warning("No valid backup found for recovery")
        return None

    def recover_from_broker(self, broker) -> Optional[dict]:
        try:
            positions = broker.get_positions()
            balance = broker.get_account_balance()
            state = {
                "positions": positions,
                "account": balance,
                "recovered_at": datetime.now().isoformat(),
                "recovery_source": "broker",
            }
            self.save_full_state(positions, [], balance)
            logger.info("Recovered state from broker")
            return state
        except Exception as e:
            logger.error("Failed to recover from broker: %s", e)
            return None

    def clear_state(self) -> None:
        for f in [self._positions_file, self._trades_file, self._account_file]:
            if f.exists():
                f.unlink()

    def _create_backup(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self._backup_dir / f"state_{timestamp}.json"
        full_state = self.load_full_state()
        full_state["backup_at"] = datetime.now().isoformat()
        self._write_json(backup_file, full_state)

        backups = sorted(self._backup_dir.glob("state_*.json"))
        while len(backups) > 10:
            oldest = backups.pop(0)
            oldest.unlink()

    def _write_json(self, filepath: Path, data: dict) -> None:
        tmp_file = filepath.with_suffix(".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            if filepath.exists():
                backup = filepath.with_suffix(".bak")
                shutil.copy2(filepath, backup)
            os.replace(tmp_file, filepath)
        except Exception as e:
            logger.error("Failed to write state file %s: %s", filepath, e)
            if tmp_file.exists():
                tmp_file.unlink()
            raise

    def _read_json(self, filepath: Path) -> Optional[dict]:
        if not filepath.exists():
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Corrupted state file %s: %s", filepath, e)
            bak_file = filepath.with_suffix(".bak")
            if bak_file.exists():
                try:
                    with open(bak_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return None
        except Exception as e:
            logger.error("Failed to read state file %s: %s", filepath, e)
            return None
