"""Daily recommend pipeline: mainboard → score → news+LLM → report."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..core.audit import get_audit_logger
from ..core.config import get_config
from ..core.env_loader import load_project_env
from .models import DailyReport
from .ranker import build_recommendations
from .reasons import ReasonEngine
from .report import ReportWriter
from .scoring import ScoringService
from .universe import UniverseBuilder

logger = logging.getLogger(__name__)


class DailyRecommendPipeline:
    def __init__(self, config_dir: str = "config", project_root: Optional[Path] = None):
        load_project_env(project_root)
        self.config_dir = config_dir
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self._cfg = get_config(config_dir)
        self._audit = get_audit_logger()
        self.universe = UniverseBuilder(config_dir)
        self.scoring = ScoringService(config_dir)
        self.reasons = ReasonEngine(config_dir)
        report_dir = self.project_root / "output" / "reports"
        self.writer = ReportWriter(str(report_dir))

    def run(
        self,
        top_n: Optional[int] = None,
        as_of: Optional[str] = None,
        universe: Optional[str] = None,
    ) -> Tuple[DailyReport, Path, Path]:
        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        top_n = int(top_n or self._cfg.get("recommend.top_n", 10))
        watch_n = int(self._cfg.get("recommend.watchlist_n", 10))
        llm_n = int(self._cfg.get("recommend.llm_candidate_n", 30))
        uni_name = universe or self._cfg.get("recommend.universe", "mainboard")

        started = datetime.now()
        symbols = self.universe.build(uni_name)
        scored = self.scoring.score_universe(symbols)
        enriched = self.scoring.enrich_with_news(scored, n=max(llm_n, top_n + watch_n))
        candidates = self.scoring.top_frame(enriched, max(llm_n, top_n + watch_n))

        snap = self.project_root / "output" / "snapshots" / as_of
        snap.mkdir(parents=True, exist_ok=True)
        if scored is not None and not scored.empty:
            scored.to_json(snap / "scored_tech.json", orient="records", force_ascii=False)
        if enriched is not None and not enriched.empty:
            enriched.to_json(snap / "scored.json", orient="records", force_ascii=False)

        analyzed = []
        for _, row in candidates.iterrows():
            result = self.reasons.analyze_row(row.to_dict(), as_of=as_of, trace_dir=snap)
            result["row"] = row.to_dict()
            analyzed.append(result)

        recs, watch = build_recommendations(analyzed, as_of, top_n, watch_n)
        overview = (
            f"主板技术打分 {len(scored)} 只，新闻增强 {len(enriched)} 只，终审分析 {len(analyzed)} 只；"
            f"产出推荐 {len(recs)}、观察 {len(watch)}。"
            f"耗时 {(datetime.now() - started).total_seconds():.1f}s。"
        )
        report = DailyReport(
            as_of=as_of,
            universe=uni_name,
            market_overview=overview,
            recommendations=recs,
            watchlist=watch,
            llm_enabled=self.reasons.llm_enabled,
            meta={
                "scored": int(len(scored)),
                "news_enriched": int(len(enriched)) if enriched is not None else 0,
                "llm_candidates": len(analyzed),
                "top_n": top_n,
                "watch_n": watch_n,
                "score_model": "tech_score + news_score → combined",
            },
        )
        md_path, json_path = self.writer.write(report)
        self._audit.log(
            "daily_recommend_complete",
            check_id="recommend.daily",
            result="OK",
            payload={
                "as_of": as_of,
                "md": str(md_path),
                "json": str(json_path),
                "top": [r.symbol for r in recs],
                "llm_enabled": report.llm_enabled,
            },
        )
        logger.info("Report written: %s", md_path)
        return report, md_path, json_path
