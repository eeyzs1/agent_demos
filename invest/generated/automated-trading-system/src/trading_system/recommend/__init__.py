"""Daily A-share recommendation package (advice only)."""

from .pipeline import DailyRecommendPipeline
from .universe import is_mainboard_code
from .news_score import NewsScorer

__all__ = ["DailyRecommendPipeline", "is_mainboard_code", "NewsScorer"]
