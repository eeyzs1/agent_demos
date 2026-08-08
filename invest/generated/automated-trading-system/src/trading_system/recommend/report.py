"""Render daily recommendation Markdown + JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

from .models import DailyReport


HINT_CN = {
    "strong_watch": "重点关注",
    "watch": "观察",
    "avoid": "暂避",
}

VALUATION_CN = {
    "cheap": "偏便宜",
    "fair": "中性",
    "expensive": "偏贵",
    "unknown": "证据不足",
}

QUALITY_CN = {
    "strong": "偏强",
    "average": "一般",
    "weak": "偏弱",
    "unknown": "证据不足",
}


class ReportWriter:
    def __init__(self, report_dir: str = "output/reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def write(self, report: DailyReport) -> Tuple[Path, Path]:
        stem = f"{report.as_of}_daily_recommend"
        md_path = self.report_dir / f"{stem}.md"
        json_path = self.report_dir / f"{stem}.json"

        md_path.write_text(self.render_markdown(report), encoding="utf-8")
        json_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return md_path, json_path

    def render_markdown(self, report: DailyReport) -> str:
        lines = [
            f"# A股每日荐股报告 · {report.as_of}",
            "",
            "## 市场概况",
            report.market_overview or "（暂无）",
            "",
            f"- 股票池：`{report.universe}`（主板）",
            f"- LLM：{'已启用' if report.llm_enabled else '未启用/降级规则模板'}",
            f"- 候选分析数：{report.meta.get('llm_candidates', 'n/a')}",
            f"- 打分样本数：{report.meta.get('scored', 'n/a')}",
            "",
            f"## 今日推荐 Top {len(report.recommendations)}",
            "",
        ]
        for rec in report.recommendations:
            lines.extend(self._section(rec))
        lines.append("## 观察池")
        lines.append("")
        if not report.watchlist:
            lines.append("（空）")
            lines.append("")
        for rec in report.watchlist:
            lines.extend(self._section(rec, compact=True))
        lines.extend(
            [
                "## 免责声明",
                "本报告由量化因子与公开新闻经模型/规则综合生成，**仅供研究参考，不构成投资建议**。",
                "股市有风险，决策需独立判断。本期不提供自动交易下单。",
                "",
            ]
        )
        return "\n".join(lines)

    def _section(self, rec, compact: bool = False) -> list:
        hint = HINT_CN.get(rec.action_hint, rec.action_hint)
        head = (
            f"### {rec.rank}. {rec.symbol} {rec.name} · 综合分 {rec.scores.get('combined_score', rec.scores.get('total', 0)):.1f} "
            f"· 建议：{hint} · **置信度 {rec.confidence:.0f}/100**"
        )
        lines = [head, ""]
        if not compact:
            lines.append("**推荐理由**")
            for i, r in enumerate(rec.reasons, 1):
                lines.append(f"{i}. {r.text}")
            lines.append("")
            s = rec.scores
            lines.append(
                f"**双指标**：技术分 {s.get('tech_score', 0):.1f}/100 | "
                f"消息分 {s.get('news_score', 0):.1f}/100 | "
                f"综合 {s.get('combined_score', s.get('total', 0)):.1f}/100"
            )
            lines.append(
                f"**辅助因子**：基本面 {s.get('fundamental', 0):.2f} | "
                f"资金 {s.get('capital_flow', 0):.2f}"
            )
            research = getattr(rec, "research", None) or {}
            if research:
                vv = VALUATION_CN.get(
                    str(research.get("valuation_view", "")),
                    str(research.get("valuation_view", "")),
                )
                qv = QUALITY_CN.get(
                    str(research.get("quality_view", "")),
                    str(research.get("quality_view", "")),
                )
                lines.append(f"**投研观**：估值 {vv or '—'} | 质量 {qv or '—'}")
                falsifiers = research.get("falsifiers") or []
                if falsifiers:
                    lines.append("**证伪条件**")
                    for f in falsifiers:
                        lines.append(f"- {f}")
                caveats = research.get("caveats") or []
                for c in caveats:
                    lines.append(f"- ⚠ {c}")
            lines.append("")
            lines.append("**主要风险**")
            for risk in rec.risks:
                lines.append(f"- {risk.text}")
            lines.append("")
            if rec.news_summary:
                lines.append(f"**新闻要点**：{rec.news_summary}")
                lines.append("")
            lines.append(f"**数据说明**：截至 {rec.as_of}；llm_status=`{rec.llm_status}`")
            lines.append("")
        else:
            one = rec.reasons[0].text if rec.reasons else ""
            research = getattr(rec, "research", None) or {}
            vv = research.get("valuation_view", "")
            qv = research.get("quality_view", "")
            research_bit = ""
            if vv or qv:
                research_bit = (
                    f" / 估值 {VALUATION_CN.get(str(vv), vv)}"
                    f" / 质量 {QUALITY_CN.get(str(qv), qv)}"
                )
            lines.append(
                f"- 技术 {rec.scores.get('tech_score', 0):.0f} / "
                f"消息 {rec.scores.get('news_score', 0):.0f} / "
                f"置信度 {rec.confidence:.0f}{research_bit}；{one}"
            )
            lines.append("")
        return lines
