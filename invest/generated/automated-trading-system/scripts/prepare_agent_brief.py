#!/usr/bin/env python3
"""Prepare agent_brief.json with tech_score + news_score + raw news for Cursor judge."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_system.core.env_loader import load_project_env
from trading_system.core.config import get_config
from trading_system.recommend.scoring import ScoringService
from trading_system.recommend.universe import UniverseBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare agent brief (dual scores)")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD")
    parser.add_argument("--top", type=int, default=None, help="Candidates for agent judge")
    parser.add_argument("--max-score", type=int, default=None, help="Cap tech scoring universe")
    parser.add_argument("--config-dir", default="config")
    args = parser.parse_args()

    load_project_env(ROOT)
    cfg = get_config(args.config_dir)
    as_of = args.as_of or datetime.now().strftime("%Y-%m-%d")
    top = int(args.top or cfg.get("recommend.llm_candidate_n", 30))
    if args.max_score is not None:
        cfg.set("recommend.max_score_stocks", int(args.max_score))

    universe = UniverseBuilder(args.config_dir)
    scoring = ScoringService(args.config_dir)

    symbols = universe.build(cfg.get("recommend.universe", "mainboard"))
    scored = scoring.score_universe(symbols)
    enriched = scoring.enrich_with_news(scored, n=top)

    snap = ROOT / "output" / "snapshots" / as_of
    snap.mkdir(parents=True, exist_ok=True)
    if scored is not None and not scored.empty:
        scored.to_json(snap / "scored_tech.json", orient="records", force_ascii=False)
    if enriched is not None and not enriched.empty:
        enriched.to_json(snap / "scored.json", orient="records", force_ascii=False)

    news_scorer = scoring._news
    items = []
    for _, row in enriched.iterrows():
        code = str(row["code"])
        ns = news_scorer.score_symbol(code)
        items.append(
            {
                "symbol": code,
                "name": str(row.get("name", "")),
                "tech_score": float(row.get("tech_score", 0)),
                "news_score": float(row.get("news_score", 50)),
                "combined_score": float(row.get("combined_score", 0)),
                "news_label": str(row.get("news_label", "")),
                "news_confidence": float(row.get("news_confidence") or 0),
                "scores": {
                    "tech_score": float(row.get("tech_score", 0)),
                    "news_score": float(row.get("news_score", 50)),
                    "combined_score": float(row.get("combined_score", 0)),
                    "technical": float(row.get("technical", 0)),
                    "fundamental": float(row.get("fundamental", 0)),
                    "capital_flow": float(row.get("capital_flow", 0)),
                },
                "news": [
                    {
                        "title": a.get("title", ""),
                        "datetime": a.get("datetime", ""),
                        "source": a.get("source", ""),
                    }
                    for a in (ns.articles or [])
                ],
                "news_keywords": ns.key_keywords,
            }
        )

    brief = {
        "as_of": as_of,
        "universe": cfg.get("recommend.universe", "mainboard"),
        "judge_mode": "cursor-agent",
        "score_model": {
            "tech_score": "RSI/MACD/MA/volume/Bollinger → 0-100",
            "news_score": "headline/body keyword polarity → 0-100",
            "combined_score": (
                f"{cfg.get('recommend.dual_scores.tech_weight', 0.6)}*tech + "
                f"{cfg.get('recommend.dual_scores.news_weight', 0.4)}*news"
            ),
        },
        "meta": {
            "scored": int(len(scored)) if scored is not None else 0,
            "candidates": len(items),
            "top_n_report": int(cfg.get("recommend.top_n", 10)),
            "watchlist_n": int(cfg.get("recommend.watchlist_n", 10)),
            "prepared_at": datetime.now().isoformat(timespec="seconds"),
        },
        "candidates": items,
        "instruction": (
            "Cursor agent: use tech_score + news_score + raw news[] to judge. "
            "Write agent_judgments.json per skill judgment-schema, then finalize."
        ),
    }
    out = snap / "agent_brief.json"
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Candidates: {len(items)} | Tech-scored universe: {brief['meta']['scored']}")
    if items:
        print(
            f"Sample {items[0]['symbol']}: tech={items[0]['tech_score']} "
            f"news={items[0]['news_score']} combined={items[0]['combined_score']} "
            f"news_n={len(items[0]['news'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
