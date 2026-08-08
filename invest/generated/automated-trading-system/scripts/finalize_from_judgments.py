#!/usr/bin/env python3
"""Merge agent_judgments.json + scores → daily recommend report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_system.core.config import get_config
from trading_system.core.env_loader import load_project_env
from trading_system.recommend.models import (
    DailyReport,
    ReasonItem,
    Recommendation,
    RiskItem,
)
from trading_system.recommend.ranker import build_recommendations
from trading_system.recommend.report import ReportWriter


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize report from agent judgments")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD")
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--watch", type=int, default=None)
    parser.add_argument("--config-dir", default="config")
    args = parser.parse_args()

    load_project_env(ROOT)
    cfg = get_config(args.config_dir)
    as_of = args.as_of or datetime.now().strftime("%Y-%m-%d")
    top_n = int(args.top or cfg.get("recommend.top_n", 10))
    watch_n = int(args.watch or cfg.get("recommend.watchlist_n", 10))

    snap = ROOT / "output" / "snapshots" / as_of
    brief_path = snap / "agent_brief.json"
    judge_path = snap / "agent_judgments.json"
    if not brief_path.exists():
        print(f"Missing brief: {brief_path}", file=sys.stderr)
        return 1
    if not judge_path.exists():
        print(f"Missing judgments: {judge_path}", file=sys.stderr)
        return 1

    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    judgments_doc = json.loads(judge_path.read_text(encoding="utf-8"))
    score_map = {c["symbol"]: c for c in brief.get("candidates", [])}
    analyzed = []

    def _f(v, default=0.0):
        try:
            if v is None:
                return float(default)
            return float(v)
        except (TypeError, ValueError):
            return float(default)

    for j in judgments_doc.get("judgments", []):
        sym = str(j.get("symbol", "")).zfill(6)
        base = score_map.get(sym) or score_map.get(j.get("symbol"))
        if not base:
            # allow judgment-only row with embedded scores
            scores = j.get("scores") or {}
            row = {
                "code": sym,
                "name": j.get("name", sym),
                "tech_score": _f(scores.get("tech_score"), 0),
                "news_score": _f(scores.get("news_score"), 50),
                "combined_score": _f(scores.get("combined_score"), 0),
                "technical": _f(scores.get("technical"), 0),
                "fundamental": _f(scores.get("fundamental"), 0),
                "capital_flow": _f(scores.get("capital_flow"), 0),
                "total": _f(scores.get("total") or scores.get("combined_score"), 0),
            }
        else:
            scores = base.get("scores") or {}
            row = {
                "code": base["symbol"],
                "name": base.get("name") or j.get("name", ""),
                "tech_score": _f(base.get("tech_score", scores.get("tech_score")), 0),
                "news_score": _f(base.get("news_score", scores.get("news_score")), 50),
                "combined_score": _f(
                    base.get("combined_score", scores.get("combined_score")), 0
                ),
                "technical": _f(scores.get("technical"), 0),
                "fundamental": _f(scores.get("fundamental"), 0),
                "capital_flow": _f(scores.get("capital_flow"), 0),
                "total": _f(
                    base.get("combined_score", scores.get("combined_score", scores.get("total"))),
                    0,
                ),
            }

        reasons = [
            ReasonItem(code=str(r.get("code", "AGENT")), text=str(r.get("text", "")), source="agent")
            for r in (j.get("reasons") or [])
            if r.get("text")
        ]
        risks = [
            RiskItem(code=str(r.get("code", "AGENT_RISK")), text=str(r.get("text", "")), source="agent")
            for r in (j.get("risks") or [])
            if r.get("text")
        ]
        analyzed.append(
            {
                "row": row,
                "action_hint": j.get("action_hint", "watch"),
                "confidence": float(j.get("confidence", 50)),
                "reasons": reasons,
                "risks": risks,
                "news_summary": j.get("news_summary", ""),
                "llm_status": "cursor-agent",
                "news_items": (base or {}).get("news") or [],
            }
        )

    if not analyzed:
        print("No judgments found", file=sys.stderr)
        return 1

    recs, watch = build_recommendations(analyzed, as_of, top_n, watch_n)
    overview = judgments_doc.get("market_overview") or (
        f"Cursor agent 终审 {len(analyzed)} 只候选；推荐 {len(recs)}，观察 {len(watch)}。"
    )
    report = DailyReport(
        as_of=as_of,
        universe=brief.get("universe", "mainboard"),
        market_overview=overview,
        recommendations=recs,
        watchlist=watch,
        llm_enabled=True,
        meta={
            "scored": brief.get("meta", {}).get("scored"),
            "llm_candidates": len(analyzed),
            "top_n": top_n,
            "watch_n": watch_n,
            "judge": judgments_doc.get("judge", "cursor-agent"),
        },
    )
    writer = ReportWriter(str(ROOT / "output" / "reports"))
    md_path, json_path = writer.write(report)
    print(f"Markdown: {md_path}")
    print(f"JSON:     {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
