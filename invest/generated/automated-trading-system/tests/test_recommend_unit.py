"""Unit tests for recommend helpers (no network)."""

from trading_system.recommend.universe import is_mainboard_code
from trading_system.recommend.reasons import ReasonEngine
from trading_system.recommend.ranker import build_recommendations
from trading_system.recommend.models import ReasonItem, RiskItem
from trading_system.recommend.report import ReportWriter
from trading_system.recommend.models import DailyReport, Recommendation


def test_mainboard_filter():
    assert is_mainboard_code("600519")
    assert is_mainboard_code("000001")
    assert is_mainboard_code("002415")
    assert not is_mainboard_code("300750")
    assert not is_mainboard_code("688981")
    assert not is_mainboard_code("830799")


def test_rule_fallback_has_reasons_and_confidence(monkeypatch):
    engine = ReasonEngine(config_dir="config")
    monkeypatch.setattr(engine._llm, "settings", engine._llm.settings)
    monkeypatch.setattr(type(engine._llm), "available", property(lambda self: False))
    monkeypatch.setattr(engine._fetcher, "get_stock_news", lambda *a, **k: [])
    payload_row = {
        "code": "600519",
        "name": "贵州茅台",
        "technical": 80,
        "fundamental": 75,
        "capital_flow": 70,
        "sentiment": 60,
        "total": 74,
    }
    result = engine.analyze_row(payload_row, as_of="2026-08-07")
    assert result["llm_status"] == "fallback"
    assert len(result["reasons"]) >= 3
    assert len(result["risks"]) >= 1
    assert 0 <= result["confidence"] <= 100


def test_report_writer(tmp_path):
    rec = Recommendation(
        symbol="600519",
        name="贵州茅台",
        as_of="2026-08-07",
        rank=1,
        scores={"technical": 80, "fundamental": 70, "capital_flow": 60, "sentiment": 50, "total": 70},
        action_hint="watch",
        confidence=77,
        reasons=[ReasonItem("A", "理由一"), ReasonItem("B", "理由二"), ReasonItem("C", "理由三")],
        risks=[RiskItem("R", "风险一")],
        news_summary="无",
        llm_status="fallback",
    )
    report = DailyReport(
        as_of="2026-08-07",
        universe="mainboard",
        market_overview="test",
        recommendations=[rec],
        watchlist=[],
        llm_enabled=False,
        meta={"scored": 1, "llm_candidates": 1},
    )
    writer = ReportWriter(str(tmp_path))
    md, js = writer.write(report)
    text = md.read_text(encoding="utf-8")
    assert "置信度 77/100" in text
    assert "600519" in text
    assert js.exists()
