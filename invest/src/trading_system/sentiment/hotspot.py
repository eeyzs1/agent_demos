from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class HotSpot:
    name: str
    score: float
    category: str
    symbols: list[str] = field(default_factory=list)
    avg_change_pct: float = 0.0
    volume_ratio: float = 1.0
    first_appeared: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    consecutive_days: int = 1
    persistence_score: float = 0.0
    momentum: str = "emerging"
    details: dict = field(default_factory=dict)


@dataclass
class SectorRotation:
    sector: str
    rank: int
    score: float
    change_pct: float
    fund_flow: float
    momentum: str
    symbols: list[str] = field(default_factory=list)


class HotSpotDetector:
    def __init__(self, persistence_window: int = 10):
        self._persistence_window = persistence_window
        self._spot_history: list[dict] = []

    def detect_hot_spots(
        self,
        sector_data: pd.DataFrame,
        top_n: int = 10,
    ) -> list[HotSpot]:
        if sector_data.empty:
            return []

        df = sector_data.copy()
        df["hot_score"] = self._calculate_hot_score(df)

        df = df.sort_values("hot_score", ascending=False).head(top_n)

        spots = []
        for _, row in df.iterrows():
            name = str(row.get("name", row.get("sector", "")))
            symbols = self._parse_symbols(row.get("symbols", ""))
            change_pct = float(row.get("change_pct", row.get("pct_change", 0)))
            vol_ratio = float(row.get("volume_ratio", 1.0))

            persistence = self._check_persistence(name)

            momentum = self._determine_momentum(
                change_pct, vol_ratio, persistence["consecutive_days"]
            )

            spot = HotSpot(
                name=name,
                score=round(float(row["hot_score"]), 2),
                category=str(row.get("category", "sector")),
                symbols=symbols,
                avg_change_pct=round(change_pct, 2),
                volume_ratio=round(vol_ratio, 2),
                consecutive_days=persistence["consecutive_days"],
                persistence_score=round(persistence["score"], 2),
                momentum=momentum,
            )
            spots.append(spot)

        self._record_spots(spots)
        return spots

    def detect_sector_rotation(
        self,
        sector_data: pd.DataFrame,
        prev_sector_data: Optional[pd.DataFrame] = None,
    ) -> list[SectorRotation]:
        if sector_data.empty:
            return []

        df = sector_data.copy()
        df["rotation_score"] = self._calculate_rotation_score(df)

        if prev_sector_data is not None and not prev_sector_data.empty:
            prev_df = prev_sector_data.copy()
            prev_df["rotation_score"] = self._calculate_rotation_score(prev_df)
            score_changes = {}
            for _, row in prev_df.iterrows():
                name = str(row.get("name", row.get("sector", "")))
                score_changes[name] = float(row.get("rotation_score", 0))

            for idx, row in df.iterrows():
                name = str(row.get("name", row.get("sector", "")))
                current = float(row.get("rotation_score", 0))
                prev = score_changes.get(name, 0)
                df.loc[idx, "score_change"] = current - prev

        df = df.sort_values("rotation_score", ascending=False)

        rotations = []
        for rank, (_, row) in enumerate(df.iterrows(), 1):
            name = str(row.get("name", row.get("sector", "")))
            change_pct = float(row.get("change_pct", row.get("pct_change", 0)))
            fund_flow = float(row.get("fund_flow", row.get("net_amount", 0)))
            symbols = self._parse_symbols(row.get("symbols", ""))

            momentum = "neutral"
            score_change = float(row.get("score_change", 0))
            if score_change > 5:
                momentum = "accelerating"
            elif score_change < -5:
                momentum = "decelerating"

            rotations.append(
                SectorRotation(
                    sector=name,
                    rank=rank,
                    score=round(float(row.get("rotation_score", 0)), 2),
                    change_pct=round(change_pct, 2),
                    fund_flow=round(fund_flow, 2),
                    momentum=momentum,
                    symbols=symbols,
                )
            )

        return rotations

    def analyze_persistence(self, spot_name: str) -> dict:
        return self._check_persistence(spot_name)

    def _calculate_hot_score(self, df: pd.DataFrame) -> pd.Series:
        change_col = "change_pct" if "change_pct" in df.columns else "pct_change"
        vol_col = "volume_ratio" if "volume_ratio" in df.columns else "turnover_rate"

        change = (
            df[change_col].fillna(0) if change_col in df.columns else pd.Series(0, index=df.index)
        )
        volume = df[vol_col].fillna(1) if vol_col in df.columns else pd.Series(1, index=df.index)

        fund_col = None
        for col in ["fund_flow", "net_amount", "main_net_inflow"]:
            if col in df.columns:
                fund_col = col
                break
        fund = df[fund_col].fillna(0) if fund_col else pd.Series(0, index=df.index)

        change_score = np.clip(change * 10, -50, 50)
        volume_score = np.clip((volume - 1) * 20, 0, 50)
        fund_score = np.clip(
            fund / (df["close"].mean() * 1e8) * 20 if df["close"].mean() > 0 else 0, -20, 20
        )

        return change_score + volume_score + fund_score + 50

    def _calculate_rotation_score(self, df: pd.DataFrame) -> pd.Series:
        change_col = "change_pct" if "change_pct" in df.columns else "pct_change"
        change = (
            df[change_col].fillna(0) if change_col in df.columns else pd.Series(0, index=df.index)
        )

        fund_col = None
        for col in ["fund_flow", "net_amount", "main_net_inflow"]:
            if col in df.columns:
                fund_col = col
                break
        fund = df[fund_col].fillna(0) if fund_col else pd.Series(0, index=df.index)

        change_score = change * 5
        fund_score = fund / 1e8 * 2 if fund_col else pd.Series(0, index=df.index)

        return change_score + fund_score + 50

    def _check_persistence(self, spot_name: str) -> dict:
        consecutive = 0
        last_seen = None
        first_seen = None

        for record in reversed(self._spot_history):
            if spot_name in record.get("spots", []):
                consecutive += 1
                if last_seen is None:
                    last_seen = record.get("timestamp")
                first_seen = record.get("timestamp")
            else:
                break

        if consecutive >= self._persistence_window:
            persistence_score = 100.0
        elif consecutive > 0:
            persistence_score = (consecutive / self._persistence_window) * 100
        else:
            persistence_score = 0.0

        return {
            "consecutive_days": consecutive,
            "score": round(persistence_score, 2),
            "first_seen": first_seen,
            "last_seen": last_seen,
        }

    def _determine_momentum(
        self, change_pct: float, volume_ratio: float, consecutive_days: int
    ) -> str:
        if consecutive_days >= 5 and change_pct > 3 and volume_ratio > 2:
            return "climax"
        elif consecutive_days >= 3 and change_pct > 2:
            return "strengthening"
        elif consecutive_days >= 2 and change_pct > 0:
            return "continuing"
        elif consecutive_days >= 1 and change_pct > 1:
            return "emerging"
        elif consecutive_days >= 1 and change_pct <= 0:
            return "weakening"
        else:
            return "fading"

    def _record_spots(self, spots: list[HotSpot]) -> None:
        self._spot_history.append(
            {
                "timestamp": datetime.now(),
                "spots": [s.name for s in spots],
                "scores": {s.name: s.score for s in spots},
            }
        )
        max_history = self._persistence_window * 2
        if len(self._spot_history) > max_history:
            self._spot_history = self._spot_history[-max_history:]

    @staticmethod
    def _parse_symbols(raw) -> list[str]:
        if isinstance(raw, str):
            return [s.strip() for s in raw.split(",") if s.strip()]
        if isinstance(raw, list):
            return raw
        return []
