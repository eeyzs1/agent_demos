import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WatchlistItem(BaseModel):
    symbol: str
    name: str = ""
    added_at: str = ""
    tags: list[str] = Field(default_factory=list)


class Watchlist(BaseModel):
    name: str
    symbols: list[WatchlistItem] = Field(default_factory=list)
    auto_fetch: bool = False


class WatchlistManager:
    def __init__(self, data_dir: str = "./data"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._watchlists_file = self._data_dir / "watchlists.json"
        self._watchlists: dict[str, Watchlist] = {}
        self._load()

    def _load(self) -> None:
        if self._watchlists_file.exists():
            try:
                with open(self._watchlists_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for name, data in raw.items():
                    self._watchlists[name] = Watchlist(**data)
            except Exception as e:
                logger.error("Failed to load watchlists: %s", e)
                self._watchlists = {}

    def _save(self) -> None:
        with open(self._watchlists_file, "w", encoding="utf-8") as f:
            json.dump(
                {name: wl.model_dump() for name, wl in self._watchlists.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def create(self, name: str, auto_fetch: bool = False) -> Watchlist:
        if name in self._watchlists:
            raise ValueError(f"Watchlist '{name}' already exists")
        wl = Watchlist(name=name, auto_fetch=auto_fetch)
        self._watchlists[name] = wl
        self._save()
        return wl

    def delete(self, name: str) -> None:
        if name not in self._watchlists:
            raise ValueError(f"Watchlist '{name}' not found")
        del self._watchlists[name]
        self._save()

    def add_symbol(
        self, watchlist_name: str, symbol: str, name: str = "", tags: Optional[list[str]] = None
    ) -> None:
        if watchlist_name not in self._watchlists:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")
        wl = self._watchlists[watchlist_name]
        existing = [item.symbol for item in wl.symbols]
        if symbol in existing:
            logger.warning("Symbol %s already in watchlist %s", symbol, watchlist_name)
            return
        from datetime import datetime

        item = WatchlistItem(
            symbol=symbol,
            name=name,
            added_at=datetime.now().isoformat(),
            tags=tags or [],
        )
        wl.symbols.append(item)
        self._save()

    def remove_symbol(self, watchlist_name: str, symbol: str) -> None:
        if watchlist_name not in self._watchlists:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")
        wl = self._watchlists[watchlist_name]
        wl.symbols = [item for item in wl.symbols if item.symbol != symbol]
        self._save()

    def get(self, name: str) -> Optional[Watchlist]:
        return self._watchlists.get(name)

    def list_all(self) -> list[Watchlist]:
        return list(self._watchlists.values())

    def get_symbols(self, name: str) -> list[str]:
        wl = self._watchlists.get(name)
        if wl is None:
            return []
        return [item.symbol for item in wl.symbols]

    def get_all_symbols(self) -> list[str]:
        seen = set()
        result = []
        for wl in self._watchlists.values():
            for item in wl.symbols:
                if item.symbol not in seen:
                    seen.add(item.symbol)
                    result.append(item.symbol)
        return result
