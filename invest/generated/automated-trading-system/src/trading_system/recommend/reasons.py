"""Combine quantitative scores + news → LLM analysis (with rule fallback)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import get_config
from ..core.env_loader import get_llm_settings
from ..data.fetcher import MarketDataFetcher
from .llm_client import LLMClient
from .models import ReasonItem, RiskItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名严谨的A股投研助手。根据「技术分 tech_score」「消息分 news_score」和「新闻原文」给出投资研究建议。
硬性要求：
1. 只输出 JSON 对象，不要 markdown。
2. 措辞用「关注/观察」，禁止「稳赚」「必涨」「强烈买入」等绝对化用语。
3. reasons 至少 3 条（尽量覆盖技术面与消息面），risks 至少 1 条；每条简短中文（≤40字）。
4. confidence 为 0-100 的整数，表示你对「值得关注」这一判断的置信度（不是预测涨幅）。
5. action_hint 只能是: strong_watch | watch | avoid
6. news_summary 用1-2句概括新闻对该股的含义；若无新闻写「暂无有效新闻」。
JSON schema:
{
  "action_hint": "watch",
  "confidence": 72,
  "reasons": [{"code": "TECH_OR_NEWS", "text": "..."}],
  "risks": [{"code": "RISK_CODE", "text": "..."}],
  "news_summary": "..."
}
"""


class ReasonEngine:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self._cfg = get_config(config_dir)
        self._fetcher = MarketDataFetcher(config_dir)
        self._llm = LLMClient()
        self._settings = get_llm_settings()

    @property
    def llm_enabled(self) -> bool:
        return bool(self._cfg.get("llm.enabled", True)) and self._llm.available

    def analyze_row(
        self,
        row: Dict[str, Any],
        as_of: str,
        trace_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        from .news_score import NewsScorer

        news_limit = int(self._cfg.get("recommend.news_per_symbol", 8))
        code = str(row.get("code") or row.get("symbol") or "").zfill(6)
        scorer = NewsScorer(self.config_dir)
        ns = scorer.score_symbol(code, limit=news_limit)
        tech_raw = row.get("tech_score")
        news_raw = row.get("news_score")
        try:
            tech_score = float(tech_raw) if tech_raw is not None and tech_raw == tech_raw else float(row.get("technical", 0)) * 100
        except (TypeError, ValueError):
            tech_score = float(row.get("technical", 0)) * 100
        try:
            news_score = float(news_raw) if news_raw is not None and news_raw == news_raw else float(ns.news_score)
        except (TypeError, ValueError):
            news_score = float(ns.news_score)
        news = ns.articles

        news_lines = []
        for n in news:
            title = str(n.get("title") or "").strip()
            dt = str(n.get("datetime") or "").strip()
            if title:
                news_lines.append(f"- [{dt}] {title}")

        payload = {
            "symbol": code,
            "name": row.get("name"),
            "as_of": as_of,
            "scores": {
                "tech_score": tech_score,
                "news_score": news_score,
                "combined_score": float(
                    row.get("combined_score")
                    or (0.6 * tech_score + 0.4 * news_score)
                ),
                "technical": float(row.get("technical", tech_score / 100.0)),
                "fundamental": float(row.get("fundamental", 0)),
                "capital_flow": float(row.get("capital_flow", 0)),
                "total": float(row.get("combined_score") or row.get("total") or tech_score),
            },
            "news": news_lines[: news_limit],
            "news_label": getattr(ns, "label", ""),
        }

        if self.llm_enabled:
            try:
                return self._llm_analyze(payload, trace_dir)
            except Exception as e:
                logger.warning("LLM analyze failed for %s: %s — fallback", row.get("code"), e)
                result = self._rule_fallback(payload)
                result["llm_status"] = "error"
                result["news_items"] = news
                return result

        result = self._rule_fallback(payload)
        result["llm_status"] = "fallback"
        result["news_items"] = news
        return result

    def _llm_analyze(self, payload: Dict[str, Any], trace_dir: Optional[Path]) -> Dict[str, Any]:
        s = payload["scores"]
        user = (
            "请基于以下材料给出 JSON 研判：\n"
            f"股票: {payload['symbol']} {payload['name']}\n"
            f"日期: {payload['as_of']}\n"
            f"tech_score: {s.get('tech_score')} /100\n"
            f"news_score: {s.get('news_score')} /100 (label={payload.get('news_label')})\n"
            f"combined_score: {s.get('combined_score')} /100\n"
            f"近期新闻:\n" + ("\n".join(payload["news"]) if payload["news"] else "(无)\n")
        )
        trace_path = None
        if trace_dir is not None and self._cfg.get("llm.save_traces", True):
            trace_path = trace_dir / f"llm_{payload['symbol']}.json"

        data = self._llm.chat_json(SYSTEM_PROMPT, user, trace_path=trace_path)
        reasons = [
            ReasonItem(code=str(r.get("code", "LLM")), text=str(r.get("text", "")), source="llm")
            for r in (data.get("reasons") or [])
            if r.get("text")
        ]
        risks = [
            RiskItem(code=str(r.get("code", "LLM_RISK")), text=str(r.get("text", "")), source="llm")
            for r in (data.get("risks") or [])
            if r.get("text")
        ]
        conf = float(data.get("confidence", 50))
        conf = max(0.0, min(100.0, conf))
        hint = str(data.get("action_hint", "watch"))
        if hint not in {"strong_watch", "watch", "avoid"}:
            hint = "watch"
        return {
            "action_hint": hint,
            "confidence": conf,
            "reasons": reasons,
            "risks": risks,
            "news_summary": str(data.get("news_summary", "")),
            "llm_status": "ok",
            "news_items": payload.get("news") or [],
        }

    def _rule_fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        s = payload["scores"]
        tech = float(s.get("tech_score", float(s.get("technical", 0)) * 100))
        news = float(s.get("news_score", 50))
        combined = float(s.get("combined_score", 0.6 * tech + 0.4 * news))
        reasons: List[ReasonItem] = []
        risks: List[RiskItem] = []

        if tech >= 65:
            reasons.append(ReasonItem("TECH_STRONG", f"技术分 {tech:.0f}，趋势/动量特征相对积极", 0.4, "rule"))
        elif tech <= 40:
            risks.append(RiskItem("TECH_WEAK", f"技术分 {tech:.0f}，短线可能承压", "rule"))
        else:
            reasons.append(ReasonItem("TECH_MID", f"技术分 {tech:.0f}，处于中性区间", 0.2, "rule"))

        if news >= 65:
            reasons.append(ReasonItem("NEWS_POS", f"消息分 {news:.0f}，标题情绪偏正面", 0.3, "news"))
        elif news <= 40:
            risks.append(RiskItem("NEWS_NEG", f"消息分 {news:.0f}，标题情绪偏负面", "news"))
        else:
            reasons.append(ReasonItem("NEWS_MID", f"消息分 {news:.0f}，情绪中性", 0.2, "news"))

        if payload.get("news"):
            reasons.append(ReasonItem("NEWS_COVER", f"近端有{len(payload['news'])}条新闻可供交叉验证", 0.1, "news"))
        else:
            risks.append(RiskItem("NEWS_NONE", "缺少有效新闻，消息分可信度低", "news"))

        while len(reasons) < 3:
            reasons.append(ReasonItem("COMBO", f"双指标综合分 {combined:.1f}", 0.1, "rule"))
        if not risks:
            risks.append(RiskItem("MKT_UNCERTAIN", "市场波动与个股事件风险始终存在", "rule"))

        base = min(90.0, max(35.0, combined))
        if payload.get("news"):
            base += 5
        else:
            base -= 8
        conf = max(0.0, min(100.0, round(base, 1)))

        hint = "watch"
        if combined >= 75 and tech >= 60 and news >= 55 and conf >= 65:
            hint = "strong_watch"
        if combined < 50 or tech < 40:
            hint = "avoid" if combined < 45 else "watch"

        return {
            "action_hint": hint,
            "confidence": conf,
            "reasons": reasons[: int(self._cfg.get("recommend.max_reasons", 5))],
            "risks": risks[: int(self._cfg.get("recommend.max_risks", 3))],
            "news_summary": (
                "暂无LLM；已用 tech_score/news_score 规则模板生成说明。"
                if not payload.get("news")
                else f"共{len(payload['news'])}条新闻标题已纳入消息分。"
            ),
            "llm_status": "fallback",
        }
