"""Tests for dual-track tech_score + news_score."""

import numpy as np
import pandas as pd

from trading_system.pipeline.screener import StockScreener
from trading_system.recommend.news_score import NewsScorer
from trading_system.recommend.report import ReportWriter
from trading_system.recommend.models import DailyReport, Recommendation, ReasonItem, RiskItem


def test_tech_score_from_ohlcv():
    n = 120
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
    df = pd.DataFrame(
        {
            "close": close,
            "volume": rng.integers(1e6, 5e6, n).astype(float),
            "change_pct": rng.normal(0, 1.5, n),
            "turnover_rate": rng.uniform(1, 8, n),
        }
    )
    s = StockScreener("config")
    tech = float(s._score_technical(df))
    assert 0.0 <= tech <= 1.0
    tech_score = round(tech * 100, 2)
    assert 0.0 <= tech_score <= 100.0


def test_news_score_positive_vs_negative():
    scorer = NewsScorer("config")
    pos = scorer.score_articles(
        "600519",
        [
            {"title": "公司业绩预增超预期获大额订单中标", "content": "盈利增长签约扩产"},
            {"title": "股东增持彰显信心", "content": "回购加码"},
        ],
    )
    neg = scorer.score_articles(
        "600519",
        [
            {"title": "业绩预减亏损扩大遭问询函", "content": "违规处罚减持风险"},
            {"title": "商誉减值暴雷跌停", "content": "诉讼违约"},
        ],
    )
    empty = scorer.score_articles("600519", [])
    assert pos.news_score > 55
    assert pos.label == "positive"
    assert neg.news_score < 45
    assert neg.label == "negative"
    assert empty.label == "no_data"
    assert empty.news_score == 50.0


def test_report_shows_dual_scores(tmp_path):
    rec = Recommendation(
        symbol="600519",
        name="贵州茅台",
        as_of="2026-08-07",
        rank=1,
        scores={
            "tech_score": 72.0,
            "news_score": 61.0,
            "combined_score": 67.6,
            "fundamental": 0.7,
            "capital_flow": 0.6,
            "total": 67.6,
        },
        action_hint="watch",
        confidence=70,
        reasons=[ReasonItem("A", "理由一"), ReasonItem("B", "理由二"), ReasonItem("C", "理由三")],
        risks=[RiskItem("R", "风险一")],
    )
    report = DailyReport(
        as_of="2026-08-07",
        universe="mainboard",
        market_overview="test",
        recommendations=[rec],
        watchlist=[],
        llm_enabled=False,
        meta={},
    )
    md, _ = ReportWriter(str(tmp_path)).write(report)
    text = md.read_text(encoding="utf-8")
    assert "技术分 72.0/100" in text
    assert "消息分 61.0/100" in text
