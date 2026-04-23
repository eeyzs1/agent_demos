import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RecommendationRecord:
    id: str
    symbol: str
    name: str = ""
    recommendation_type: str = ""
    price: float = 0.0
    score: float = 0.0
    rating: str = ""
    reasons: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    return_1d: Optional[float] = None
    return_3d: Optional[float] = None
    return_5d: Optional[float] = None
    return_10d: Optional[float] = None
    actual_max_price: Optional[float] = None
    actual_min_price: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "recommendation_type": self.recommendation_type,
            "price": self.price,
            "score": self.score,
            "rating": self.rating,
            "reasons": self.reasons,
            "created_at": self.created_at.isoformat(),
            "return_1d": self.return_1d,
            "return_3d": self.return_3d,
            "return_5d": self.return_5d,
            "return_10d": self.return_10d,
        }


@dataclass
class PerformanceStats:
    total_recommendations: int = 0
    accurate_count: int = 0
    accuracy_rate: float = 0.0
    avg_return_1d: float = 0.0
    avg_return_3d: float = 0.0
    avg_return_5d: float = 0.0
    avg_return_10d: float = 0.0
    sharpe_ratio: float = 0.0
    by_rating: dict = field(default_factory=dict)


class RecommendationTracker:
    def __init__(self, db=None):
        self._records: list[RecommendationRecord] = []
        self._db = db
        self._counter = 0

    def record_recommendation(
        self,
        symbol: str,
        name: str = "",
        recommendation_type: str = "",
        price: float = 0.0,
        score: float = 0.0,
        rating: str = "",
        reasons: Optional[list[str]] = None,
    ) -> RecommendationRecord:
        self._counter += 1
        rec = RecommendationRecord(
            id=f"REC-{self._counter:06d}",
            symbol=symbol,
            name=name,
            recommendation_type=recommendation_type,
            price=price,
            score=score,
            rating=rating,
            reasons=reasons or [],
        )
        self._records.append(rec)
        logger.info("Recorded recommendation: %s %s", rec.id, symbol)
        return rec

    def update_returns(self, symbol: str, current_prices: dict[str, float]) -> None:
        for rec in self._records:
            if rec.symbol != symbol:
                continue
            if not current_prices:
                continue
            current_price = current_prices.get(symbol)
            if current_price is None or rec.price <= 0:
                continue

            days_held = (datetime.now() - rec.created_at).days
            ret = (current_price - rec.price) / rec.price * 100

            if days_held >= 1 and rec.return_1d is None:
                rec.return_1d = round(ret, 2)
            if days_held >= 3 and rec.return_3d is None:
                rec.return_3d = round(ret, 2)
            if days_held >= 5 and rec.return_5d is None:
                rec.return_5d = round(ret, 2)
            if days_held >= 10 and rec.return_10d is None:
                rec.return_10d = round(ret, 2)

    def get_stats(self, days: int = 30) -> PerformanceStats:
        cutoff = datetime.now().timestamp() - days * 86400
        recent = [r for r in self._records if r.created_at.timestamp() >= cutoff]

        if not recent:
            return PerformanceStats()

        buy_records = [r for r in recent if r.recommendation_type == "买入"]
        accurate = [r for r in buy_records if r.return_5d is not None and r.return_5d > 0]

        returns_1d = [r.return_1d for r in buy_records if r.return_1d is not None]
        returns_3d = [r.return_3d for r in buy_records if r.return_3d is not None]
        returns_5d = [r.return_5d for r in buy_records if r.return_5d is not None]
        returns_10d = [r.return_10d for r in buy_records if r.return_10d is not None]

        by_rating = {}
        for r in recent:
            if r.rating not in by_rating:
                by_rating[r.rating] = {"count": 0, "accurate": 0}
            by_rating[r.rating]["count"] += 1
            if r.return_5d is not None and r.return_5d > 0:
                by_rating[r.rating]["accurate"] += 1

        all_returns = returns_1d or returns_3d or returns_5d or [0]
        sharpe = np.mean(all_returns) / np.std(all_returns) if len(all_returns) > 1 and np.std(all_returns) > 0 else 0

        return PerformanceStats(
            total_recommendations=len(recent),
            accurate_count=len(accurate),
            accuracy_rate=round(len(accurate) / len(buy_records) * 100, 2) if buy_records else 0,
            avg_return_1d=round(np.mean(returns_1d), 2) if returns_1d else 0,
            avg_return_3d=round(np.mean(returns_3d), 2) if returns_3d else 0,
            avg_return_5d=round(np.mean(returns_5d), 2) if returns_5d else 0,
            avg_return_10d=round(np.mean(returns_10d), 2) if returns_10d else 0,
            sharpe_ratio=round(float(sharpe), 2),
            by_rating=by_rating,
        )

    def generate_performance_report(self, days: int = 30) -> str:
        stats = self.get_stats(days)
        lines = [
            f"# 推荐绩效报告（近{days}天）",
            "",
            f"- 总推荐数: {stats.total_recommendations}",
            f"- 准确数: {stats.accurate_count}",
            f"- 准确率: {stats.accuracy_rate:.1f}%",
            f"- 平均1日收益: {stats.avg_return_1d:.2f}%",
            f"- 平均3日收益: {stats.avg_return_3d:.2f}%",
            f"- 平均5日收益: {stats.avg_return_5d:.2f}%",
            f"- 平均10日收益: {stats.avg_return_10d:.2f}%",
            f"- 夏普比: {stats.sharpe_ratio:.2f}",
        ]
        if stats.by_rating:
            lines.append("")
            lines.append("## 按评级统计")
            for rating, data in stats.by_rating.items():
                lines.append(f"- {rating}: {data['count']}条, 准确{data['accurate']}条")
        return "\n".join(lines)

    @property
    def records(self) -> list[RecommendationRecord]:
        return list(self._records)
