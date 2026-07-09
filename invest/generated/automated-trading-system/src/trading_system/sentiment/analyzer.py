"""SentimentAnalyzer — 6-dimensional market sentiment scoring.

Computes weighted market sentiment across six dimensions:
1. 涨跌家数比 (advance/decline ratio) - 20% weight
2. 涨跌停比 (limit up/down ratio) - 15% weight
3. 换手率 (turnover rate analysis) - 15% weight
4. 新高新低比 (new high/low ratio) - 15% weight
5. 融资融券 (margin trading balance change) - 15% weight
6. 指数趋势 (index trend analysis) - 20% weight

Output: 5-level sentiment score (强烈看多/看多/中性/看空/强烈看空)
        hotspot momentum labels
Depends only on data and core, NOT on risk or execution.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.event_bus import get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class DimensionScore:
    """Score for a single sentiment dimension."""

    name: str
    raw_value: float
    normalized_score: float  # 0-1
    weight: float
    weighted_score: float
    description: str = ""


@dataclass
class SentimentResult:
    """Complete sentiment analysis result."""

    overall_score: float  # 0-1
    weighted_score: float  # 0-1
    level: str  # 强烈看多/看多/中性/看空/强烈看空
    dimensions: Dict[str, DimensionScore] = field(default_factory=dict)
    hotspots: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
    confidence: float = 1.0  # 0-1 based on data completeness


class SentimentAnalyzer:
    """6-dimensional market sentiment analyzer.

    Performs weighted sentiment analysis across six market breadth
    and momentum dimensions. Publishes "sentiment.analysis_complete" event.
    """

    # Sentiment level thresholds (overall_score 0-1)
    LEVEL_THRESHOLDS: List[Tuple[float, str]] = [
        (0.85, "强烈看多"),
        (0.65, "看多"),
        (0.35, "中性"),
        (0.15, "看空"),
        (0.0, "强烈看空"),
    ]

    def __init__(self, config_dir: str = "config") -> None:
        """Initialize the sentiment analyzer.

        Args:
            config_dir: Path to configuration directory.
        """
        config = get_config(config_dir)
        self._config = config
        self._event_bus = get_event_bus()
        self._audit = get_audit_logger()

        # Load weights from config or use defaults
        self._weights: Dict[str, float] = {
            "advance_decline": config.get("sentiment.weights.advance_decline", 0.20),
            "limit_ratio": config.get("sentiment.weights.limit_ratio", 0.15),
            "turnover": config.get("sentiment.weights.turnover", 0.15),
            "new_high_low": config.get("sentiment.weights.new_high_low", 0.15),
            "margin": config.get("sentiment.weights.margin", 0.15),
            "index_trend": config.get("sentiment.weights.index_trend", 0.20),
        }

        # Verify weights sum to ~1.0
        total_weight = sum(self._weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(
                "Sentiment weights sum to %.3f, normalizing to 1.0", total_weight
            )
            for key in self._weights:
                self._weights[key] /= total_weight

        # Thresholds from config
        self._thresholds: Dict[str, float] = {
            "advance_decline_bullish": config.get(
                "sentiment.thresholds.advance_decline_bullish", 1.5
            ),
            "advance_decline_bearish": config.get(
                "sentiment.thresholds.advance_decline_bearish", 0.67
            ),
            "limit_up_minimum": config.get(
                "sentiment.thresholds.limit_up_minimum", 20
            ),
            "high_turnover_pct": config.get(
                "sentiment.thresholds.high_turnover_pct", 1.5
            ),
            "low_turnover_pct": config.get(
                "sentiment.thresholds.low_turnover_pct", 0.7
            ),
            "margin_change_bullish": config.get(
                "sentiment.thresholds.margin_change_bullish", 0.02
            ),
            "margin_change_bearish": config.get(
                "sentiment.thresholds.margin_change_bearish", -0.02
            ),
        }

        # Cached result
        self._last_result: Optional[SentimentResult] = None

        logger.info(
            "SentimentAnalyzer initialized with weights: %s", str(self._weights)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, market_data: Dict[str, Any]) -> SentimentResult:
        """Perform 6-dimensional sentiment analysis on market data.

        Args:
            market_data: Dictionary containing market breadth data with keys:
                - advancing: number of advancing stocks
                - declining: number of declining stocks
                - limit_up: number of limit-up stocks
                - limit_down: number of limit-down stocks
                - total_stocks: total number of traded stocks
                - current_turnover: total market turnover (billion CNY)
                - avg_turnover_20d: 20-day average turnover
                - new_highs: number of stocks making new 52-week highs
                - new_lows: number of stocks making new 52-week lows
                - margin_balance: current margin balance
                - margin_balance_prev: previous day margin balance
                - index_closes: list of recent index close prices
                - hotspots: optional list of hotspot sector data

        Returns:
            SentimentResult with overall score, level, dimension breakdowns,
            and hotspot momentum labels.
        """
        dimensions: Dict[str, DimensionScore] = {}
        total_weighted = 0.0
        missing_count = 0

        # 1. 涨跌家数比 (advance/decline ratio) - 20%
        dim = "advance_decline"
        try:
            advancing = int(market_data.get("advancing", 0))
            declining = int(market_data.get("declining", 0))
            dimensions[dim] = self._score_advance_decline(advancing, declining)
            total_weighted += dimensions[dim].weighted_score
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Missing data for advance/decline: %s", e)
            dimensions[dim] = self._neutral_dim(dim, "Missing data")
            total_weighted += dimensions[dim].weighted_score
            missing_count += 1

        # 2. 涨跌停比 (limit up/down ratio) - 15%
        dim = "limit_ratio"
        try:
            limit_up = int(market_data.get("limit_up", 0))
            limit_down = int(market_data.get("limit_down", 0))
            total_stocks = int(market_data.get("total_stocks", 1))
            dimensions[dim] = self._score_limit_ratio(limit_up, limit_down, total_stocks)
            total_weighted += dimensions[dim].weighted_score
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Missing data for limit ratio: %s", e)
            dimensions[dim] = self._neutral_dim(dim, "Missing data")
            total_weighted += dimensions[dim].weighted_score
            missing_count += 1

        # 3. 换手率 (turnover rate analysis) - 15%
        dim = "turnover"
        try:
            curr_turnover = float(market_data.get("current_turnover", 0))
            avg_turnover = float(market_data.get("avg_turnover_20d", 0))
            dimensions[dim] = self._score_turnover(curr_turnover, avg_turnover)
            total_weighted += dimensions[dim].weighted_score
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Missing data for turnover: %s", e)
            dimensions[dim] = self._neutral_dim(dim, "Missing data")
            total_weighted += dimensions[dim].weighted_score
            missing_count += 1

        # 4. 新高新低比 (new high/low ratio) - 15%
        dim = "new_high_low"
        try:
            new_highs = int(market_data.get("new_highs", 0))
            new_lows = int(market_data.get("new_lows", 0))
            total_stocks = int(market_data.get("total_stocks", 1))
            dimensions[dim] = self._score_new_high_low(new_highs, new_lows, total_stocks)
            total_weighted += dimensions[dim].weighted_score
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Missing data for new high/low: %s", e)
            dimensions[dim] = self._neutral_dim(dim, "Missing data")
            total_weighted += dimensions[dim].weighted_score
            missing_count += 1

        # 5. 融资融券 (margin trading balance change) - 15%
        dim = "margin"
        try:
            curr_margin = float(market_data.get("margin_balance", 0))
            prev_margin = float(market_data.get("margin_balance_prev", 0))
            dimensions[dim] = self._score_margin_change(curr_margin, prev_margin)
            total_weighted += dimensions[dim].weighted_score
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Missing data for margin: %s", e)
            dimensions[dim] = self._neutral_dim(dim, "Missing data")
            total_weighted += dimensions[dim].weighted_score
            missing_count += 1

        # 6. 指数趋势 (index trend analysis) - 20%
        dim = "index_trend"
        try:
            index_closes = market_data.get("index_closes", [])
            if not isinstance(index_closes, list):
                index_closes = []
            dimensions[dim] = self._score_index_trend(index_closes)
            total_weighted += dimensions[dim].weighted_score
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Missing data for index trend: %s", e)
            dimensions[dim] = self._neutral_dim(dim, "Missing data")
            total_weighted += dimensions[dim].weighted_score
            missing_count += 1

        # Confidence and level
        confidence = (6 - missing_count) / 6.0
        overall_score = total_weighted
        level = self._get_level(overall_score)

        # Process hotspots
        hotspots = self._process_hotspots(market_data.get("hotspots", []))

        result = SentimentResult(
            overall_score=overall_score,
            weighted_score=overall_score,
            level=level,
            dimensions=dimensions,
            hotspots=hotspots,
            timestamp=datetime.now().isoformat(),
            confidence=confidence,
        )

        self._last_result = result

        # Audit log
        self._audit.log(
            "sentiment_analysis",
            check_id="full_analysis",
            result="OK",
            actor="sentiment_analyzer",
            payload={
                "overall_score": overall_score,
                "level": level,
                "confidence": confidence,
                "hotspot_count": len(hotspots),
            },
        )

        # Publish event
        self._event_bus.publish(
            "sentiment.analysis_complete",
            {
                "overall_score": overall_score,
                "level": level,
                "confidence": confidence,
                "hotspots": hotspots,
                "timestamp": result.timestamp,
            },
            source="sentiment.analyzer",
        )

        logger.info(
            "Sentiment analysis complete: score=%.3f level=%s confidence=%.1f%%",
            overall_score, level, confidence * 100,
        )
        return result

    def get_score(self) -> Tuple[Optional[float], Optional[str]]:
        """Get the most recent analysis overall score and level.

        Returns:
            (overall_score, sentiment_level) or (None, None) if no analysis done.
        """
        if self._last_result is None:
            return (None, None)
        return (self._last_result.overall_score, self._last_result.level)

    def get_hotspots(self) -> List[Dict[str, Any]]:
        """Get the most recent analysis hotspot momentum labels.

        Returns:
            List of annotated hotspots or empty list if no analysis done.
        """
        if self._last_result is None:
            return []
        return self._last_result.hotspots

    def get_detailed_result(self) -> Optional[SentimentResult]:
        """Get the full detailed result from last analysis.

        Returns:
            SentimentResult object or None if no analysis done.
        """
        return self._last_result

    # ------------------------------------------------------------------
    # Dimension Scoring Methods
    # ------------------------------------------------------------------

    def _neutral_dim(self, name: str, reason: str = "Missing data") -> DimensionScore:
        """Create a neutral fallback dimension score."""
        w = self._weights.get(name, 0.15)
        return DimensionScore(
            name=name, raw_value=0.0, normalized_score=0.5,
            weight=w, weighted_score=0.5 * w, description=reason,
        )

    def _score_advance_decline(
        self, advancing: int, declining: int
    ) -> DimensionScore:
        """Score advance/decline ratio. Higher = bullish."""
        w = self._weights["advance_decline"]
        if advancing + declining == 0:
            return DimensionScore(
                name="advance_decline", raw_value=0.0, normalized_score=0.5,
                weight=w, weighted_score=0.5 * w,
                description="No advance/decline data",
            )

        ratio = advancing / max(declining, 1)
        bull = self._thresholds["advance_decline_bullish"]
        bear = self._thresholds["advance_decline_bearish"]

        if ratio >= bull:
            normalized = 1.0
        elif ratio <= bear:
            normalized = 0.0
        else:
            normalized = (ratio - bear) / (bull - bear)

        return DimensionScore(
            name="advance_decline", raw_value=ratio,
            normalized_score=normalized, weight=w,
            weighted_score=normalized * w,
            description=f"adv={advancing}, dec={declining}, ratio={ratio:.2f}",
        )

    def _score_limit_ratio(
        self, limit_up: int, limit_down: int, total_stocks: int
    ) -> DimensionScore:
        """Score limit up/down ratio. More limit-ups = bullish."""
        w = self._weights["limit_ratio"]
        total = limit_up + limit_down
        if total == 0:
            return DimensionScore(
                name="limit_ratio", raw_value=0.5, normalized_score=0.5,
                weight=w, weighted_score=0.5 * w,
                description="No limit moves today",
            )

        up_ratio = limit_up / total
        normalized = up_ratio
        min_up = self._thresholds["limit_up_minimum"]
        if limit_up >= min_up and up_ratio > 0.7:
            normalized = min(1.0, normalized + 0.1)

        return DimensionScore(
            name="limit_ratio", raw_value=up_ratio,
            normalized_score=normalized, weight=w,
            weighted_score=normalized * w,
            description=f"up={limit_up}, down={limit_down}, up_ratio={up_ratio:.2f}",
        )

    def _score_turnover(
        self, current: float, avg_20d: float
    ) -> DimensionScore:
        """Score turnover rate. Higher = bullish (strong participation)."""
        w = self._weights["turnover"]
        if avg_20d <= 0 or current <= 0:
            return DimensionScore(
                name="turnover", raw_value=0.0, normalized_score=0.5,
                weight=w, weighted_score=0.5 * w,
                description="Missing turnover data",
            )

        ratio = current / avg_20d
        hi = self._thresholds["high_turnover_pct"]
        lo = self._thresholds["low_turnover_pct"]

        if ratio >= hi:
            normalized = 0.8 if ratio < 3.0 else 0.6  # extremely high = panic
        elif ratio <= lo:
            normalized = 0.2
        else:
            t = (ratio - lo) / (hi - lo)
            normalized = 0.3 + t * 0.4

        return DimensionScore(
            name="turnover", raw_value=ratio,
            normalized_score=normalized, weight=w,
            weighted_score=normalized * w,
            description=f"current={current:.1f}, avg={avg_20d:.1f}, ratio={ratio:.2f}",
        )

    def _score_new_high_low(
        self, new_highs: int, new_lows: int, total_stocks: int
    ) -> DimensionScore:
        """Score new highs vs new lows ratio. Many highs = bullish."""
        w = self._weights["new_high_low"]
        total = new_highs + new_lows
        if total == 0:
            return DimensionScore(
                name="new_high_low", raw_value=0.0, normalized_score=0.5,
                weight=w, weighted_score=0.5 * w,
                description="No new highs or lows",
            )

        high_ratio = new_highs / total
        normalized = high_ratio

        pct_high = new_highs / max(total_stocks, 1)
        if pct_high > 0.05:
            normalized = min(1.0, normalized + 0.15)
        pct_low = new_lows / max(total_stocks, 1)
        if pct_low > 0.05:
            normalized = max(0.0, normalized - 0.15)

        return DimensionScore(
            name="new_high_low", raw_value=high_ratio,
            normalized_score=normalized, weight=w,
            weighted_score=normalized * w,
            description=f"highs={new_highs}, lows={new_lows}, ratio={high_ratio:.2f}",
        )

    def _score_margin_change(
        self, current: float, prev: float
    ) -> DimensionScore:
        """Score margin trading balance change. Increasing = bullish."""
        w = self._weights["margin"]
        if prev <= 0:
            return DimensionScore(
                name="margin", raw_value=0.0, normalized_score=0.5,
                weight=w, weighted_score=0.5 * w,
                description="No previous margin data",
            )

        change_pct = (current - prev) / prev
        bull = self._thresholds["margin_change_bullish"]
        bear = self._thresholds["margin_change_bearish"]

        if change_pct >= bull:
            normalized = 0.8 + 0.2 * min(1.0, change_pct / 0.1)
        elif change_pct <= bear:
            normalized = 0.2 - 0.2 * max(0.0, abs(change_pct) / 0.1)
        else:
            normalized = 0.5 + (change_pct / (bull - bear))
        normalized = max(0.0, min(1.0, normalized))

        return DimensionScore(
            name="margin", raw_value=change_pct,
            normalized_score=normalized, weight=w,
            weighted_score=normalized * w,
            description=f"change_pct={change_pct * 100:.2f}%",
        )

    def _score_index_trend(self, closes: List[float]) -> DimensionScore:
        """Score index trend based on MA20/MA50 and daily momentum."""
        w = self._weights["index_trend"]
        if len(closes) < 50:
            return DimensionScore(
                name="index_trend", raw_value=0.0, normalized_score=0.5,
                weight=w, weighted_score=0.5 * w,
                description=f"Insufficient data: {len(closes)} < 50",
            )

        arr = np.array(closes[-60:], dtype=float)
        ma20 = float(np.mean(arr[-20:]))
        ma50 = float(np.mean(arr))
        current = arr[-1]

        diffs = np.diff(arr[-20:])
        up_days = int(np.sum(diffs > 0))
        down_days = int(np.sum(diffs < 0))

        score = 0.0
        if current > ma20:
            score += 0.25
        if current > ma50:
            score += 0.25
        if ma20 > ma50:
            score += 0.25
        if up_days + down_days > 0:
            score += 0.25 * (up_days / (up_days + down_days))

        normalized = max(0.0, min(1.0, score))

        if normalized > 0.6:
            trend = "bullish"
        elif normalized < 0.4:
            trend = "bearish"
        else:
            trend = "neutral"

        return DimensionScore(
            name="index_trend", raw_value=normalized,
            normalized_score=normalized, weight=w,
            weighted_score=normalized * w,
            description=(
                f"current={current:.2f}, MA20={ma20:.2f}, MA50={ma50:.2f}, "
                f"up_days={up_days}, trend={trend}"
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_level(self, overall_score: float) -> str:
        """Map 0-1 score to 5-level classification."""
        for threshold, level in self.LEVEL_THRESHOLDS:
            if overall_score >= threshold:
                return level
        return "强烈看空"

    def _process_hotspots(
        self, hotspot_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process sector hotspot data and add momentum labels.

        Args:
            hotspot_data: List of dicts with keys:
                - sector: sector name/code
                - advance_count: number of advancing stocks in sector
                - decline_count: number of declining stocks
                - avg_change_pct: average price change percent
                - volume_ratio: volume vs 20d average

        Returns:
            Annotated hotspots with momentum labels, sorted by momentum.
        """
        if not isinstance(hotspot_data, list):
            return []

        processed: List[Dict[str, Any]] = []
        for hs in hotspot_data:
            if not isinstance(hs, dict):
                continue

            sector = hs.get("sector", "unknown")
            adv = float(hs.get("advance_count", 0))
            dec = float(hs.get("decline_count", 0))
            avg_chg = float(hs.get("avg_change_pct", 0))
            vol_ratio = float(hs.get("volume_ratio", 1.0))

            breadth_score = adv / (adv + dec) if adv + dec > 0 else 0.5
            norm_chg = max(-1.0, min(1.0, avg_chg / 5.0))
            change_score = (norm_chg + 1.0) / 2.0
            vol_score = min(1.0, max(0.0, vol_ratio / 2.0))

            momentum = breadth_score * 0.4 + change_score * 0.4 + vol_score * 0.2

            if momentum >= 0.75:
                label = "强动量"
            elif momentum >= 0.6:
                label = "中动量"
            elif momentum >= 0.4:
                label = "弱动量"
            else:
                label = "负动量"

            processed.append({
                "sector": sector,
                "momentum_score": round(momentum, 4),
                "momentum_label": label,
                "breadth_score": round(breadth_score, 4),
                "avg_change_pct": avg_chg,
                "volume_ratio": vol_ratio,
            })

        processed.sort(key=lambda x: x["momentum_score"], reverse=True)
        return processed