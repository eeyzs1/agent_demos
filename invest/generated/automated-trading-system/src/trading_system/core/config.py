"""ConfigManager — YAML configuration with hot-reload support.

Loads configuration from YAML files. Supports nested key access, default
value merging, and file-watch based hot-reload.

All configuration must be in YAML files, no hardcoded values (AR009).
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages YAML configuration with hot-reload support.

    Loads config from a directory of YAML files. Supports nested key access
    via dot-separated paths (e.g., 'risk.max_drawdown_pct').

    Hot-reload watches file modification times and reloads on change.
    """

    def __init__(self, config_dir: str = "config", default_config: Dict = None):
        self._config_dir = Path(config_dir)
        self._config: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = default_config or {}
        self._lock = threading.RLock()
        self._file_mtimes: Dict[str, float] = {}
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_interval = 5.0
        self._running = False

        self.load()

    def load(self) -> None:
        """Load all YAML files from the config directory."""
        with self._lock:
            self._config = dict(self._defaults)
            self._file_mtimes.clear()

            if self._config_dir.exists():
                for yaml_file in sorted(self._config_dir.glob("*.yaml")):
                    try:
                        with open(yaml_file, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                        if isinstance(data, dict):
                            self._config.update(data)
                        self._file_mtimes[str(yaml_file)] = yaml_file.stat().st_mtime
                        logger.debug("Loaded config: %s", yaml_file.name)
                    except Exception:
                        logger.exception("Failed to load config: %s", yaml_file)

            logger.info("Configuration loaded: %d keys", len(self._config))

    def _check_and_reload(self) -> bool:
        """Check for file changes and reload if needed.

        Returns:
            True if config was reloaded.
        """
        changed = False
        if self._config_dir.exists():
            for yaml_file in self._config_dir.glob("*.yaml"):
                key = str(yaml_file)
                try:
                    mtime = yaml_file.stat().st_mtime
                    if key not in self._file_mtimes or self._file_mtimes[key] != mtime:
                        changed = True
                        self._file_mtimes[key] = mtime
                except OSError:
                    pass

        if changed:
            logger.info("Config file change detected, reloading...")
            self.load()
            return True
        return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-separated key.

        Args:
            key: Dot-separated path (e.g., 'risk.max_drawdown_pct').
            default: Default value if key not found.

        Returns:
            The configuration value.
        """
        with self._lock:
            parts = key.split(".")
            value = self._config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value at runtime (does not persist to disk)."""
        with self._lock:
            parts = key.split(".")
            target = self._config
            for part in parts[:-1]:
                if part not in target or not isinstance(target[part], dict):
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value

    def get_all(self) -> Dict[str, Any]:
        """Get a copy of all configuration."""
        with self._lock:
            return dict(self._config)

    def start_hot_reload(self, interval: float = 5.0) -> None:
        """Start background thread for hot-reload.

        Args:
            interval: Check interval in seconds.
        """
        if self._running:
            return

        self._watch_interval = interval
        self._running = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="config-hot-reload"
        )
        self._watch_thread.start()
        logger.info("Hot-reload started (interval=%ss)", interval)

    def stop_hot_reload(self) -> None:
        """Stop the hot-reload background thread."""
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=10)
            self._watch_thread = None

    def _watch_loop(self) -> None:
        """Background loop that checks for config file changes."""
        while self._running:
            time.sleep(self._watch_interval)
            try:
                self._check_and_reload()
            except Exception:
                logger.exception("Error in config watch loop")


# Global singleton
_config_manager: ConfigManager = None


def get_config(config_dir: str = "config") -> ConfigManager:
    """Get or create the global ConfigManager singleton."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir=config_dir)
    return _config_manager