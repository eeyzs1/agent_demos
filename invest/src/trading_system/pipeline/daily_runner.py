import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from trading_system.advisor.daily_report import DailyReportGenerator
from trading_system.advisor.entry_exit import EntryExitAdvisor
from trading_system.data.store import DataStore
from trading_system.pipeline.fusion import DecisionFusionEngine, FusionDecision
from trading_system.pipeline.scan_recommend import ScanRecommendPipeline
from trading_system.scorer.engine import StockScorer, StockScore

logger = logging.getLogger(__name__)


class DailyJobRunner:
    def __init__(
        self,
        output_dir: str = "./output",
        data_store: Optional[DataStore] = None,
    ):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._store = data_store or DataStore()

        self._scorer = StockScorer()
        self._advisor = EntryExitAdvisor(self._scorer)
        self._report_gen = DailyReportGenerator(
            scorer=self._scorer, advisor=self._advisor, output_dir=str(self._output_dir),
        )

    def run_daily(
        self,
        candidate_limit: int = 100,
        top_n: int = 20,
    ) -> dict:
        start_time = datetime.now()
        logger.info("========== 每日自动化交易任务开始 ==========")

        logger.info("[1/4] 全市场扫描...")
        pipeline = ScanRecommendPipeline()
        stock_data_list, market_summary = pipeline.run(candidate_limit=candidate_limit)
        logger.info("扫描完成: %d 只股票", len(stock_data_list))

        if not stock_data_list:
            logger.error("未获取到有效股票数据")
            return {"status": "failed", "error": "no_stock_data", "timestamp": start_time.isoformat()}

        logger.info("[2/4] 多因子评分...")
        scores: list[StockScore] = self._scorer.rank_stocks(stock_data_list)
        logger.info("评分完成: %d 只, 最高分 %.1f", len(scores), scores[0].total_score if scores else 0)

        logger.info("[3/4] 策略融合决策...")
        fusion_engine = DecisionFusionEngine(data_store=self._store)
        fusion_decisions: list[FusionDecision] = fusion_engine.fuse(scores, stock_data_list, top_n=min(top_n, len(scores)))
        logger.info("融合完成: %d 条决策", len(fusion_decisions))

        buy_decisions = [d for d in fusion_decisions if d.fusion_action == "BUY"]
        sell_decisions = [d for d in fusion_decisions if d.fusion_action == "SELL"]
        logger.info("决策分布: BUY=%d, SELL=%d, HOLD=%d",
                    len(buy_decisions), len(sell_decisions),
                    len(fusion_decisions) - len(buy_decisions) - len(sell_decisions))

        logger.info("[4/4] 生成报告...")
        recommendations = []
        for d in fusion_decisions:
            try:
                rec = self._advisor.recommend_entry(d.symbol, d.price, d.data)
                rec.confidence = d.fusion_confidence
                recommendations.append(rec)
            except Exception as e:
                logger.warning("推荐生成失败 %s: %s", d.symbol, e)

        self._report_gen.generate_report(scores, recommendations, market_summary)

        signals_path = self._save_trade_signals(fusion_decisions, market_summary)
        logger.info("交易信号已保存: %s", signals_path)

        summary_path = self._save_daily_summary(
            fusion_decisions, scores, market_summary, start_time
        )
        logger.info("每日汇总已保存: %s", summary_path)

        elapsed = (datetime.now() - start_time).total_seconds()
        result = {
            "status": "success",
            "timestamp": start_time.isoformat(),
            "elapsed_seconds": round(elapsed, 1),
            "stocks_scanned": len(stock_data_list),
            "stocks_scored": len(scores),
            "fusion_decisions": len(fusion_decisions),
            "buy_count": len(buy_decisions),
            "sell_count": len(sell_decisions),
            "hold_count": len(fusion_decisions) - len(buy_decisions) - len(sell_decisions),
            "top_buy": [d.to_dict() for d in buy_decisions[:5]],
            "report_dir": str(self._output_dir),
            "signals_file": str(signals_path),
            "summary_file": str(summary_path),
        }

        logger.info("========== 每日任务完成 (耗时 %s秒) ==========", elapsed)
        return result

    def _save_trade_signals(self, decisions: list[FusionDecision], market_summary: dict) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = self._output_dir / f"trade_signals_{date_str}.json"

        signals = {
            "generated_at": datetime.now().isoformat(),
            "date": date_str,
            "market_summary": market_summary,
            "total_decisions": len(decisions),
            "decisions": [d.to_dict() for d in decisions],
        }

        path.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _save_daily_summary(
        self,
        decisions: list[FusionDecision],
        scores: list[StockScore],
        market_summary: dict,
        start_time: datetime,
    ) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = self._output_dir / f"daily_summary_{date_str}.json"

        summary = {
            "date": date_str,
            "generated_at": datetime.now().isoformat(),
            "elapsed_seconds": round((datetime.now() - start_time).total_seconds(), 1),
            "market_summary": market_summary,
            "statistics": {
                "total_decisions": len(decisions),
                "buy_decisions": sum(1 for d in decisions if d.fusion_action == "BUY"),
                "sell_decisions": sum(1 for d in decisions if d.fusion_action == "SELL"),
                "hold_decisions": sum(1 for d in decisions if d.fusion_action == "HOLD"),
                "avg_fusion_confidence": round(
                    sum(d.fusion_confidence for d in decisions) / max(len(decisions), 1), 4,
                ),
                "avg_scorer_score": round(
                    sum(s.total_score for s in scores) / max(len(scores), 1), 1,
                ),
            },
            "top_10_buy": [d.to_dict() for d in decisions if d.fusion_action == "BUY"][:10],
            "top_10_scored": [
                {"symbol": s.symbol, "name": s.name, "score": s.total_score, "rating": s.rating.value}
                for s in scores[:10]
            ],
        }

        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return path