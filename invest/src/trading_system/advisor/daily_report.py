import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from trading_system.advisor.entry_exit import EntryExitAdvisor, TradeRecommendation
from trading_system.scorer.engine import StockScore, StockScorer

logger = logging.getLogger(__name__)


class DailyReportGenerator:
    def __init__(
        self,
        scorer: Optional[StockScorer] = None,
        advisor: Optional[EntryExitAdvisor] = None,
        output_dir: str = "./output",
        notification_manager=None,
    ):
        self._scorer = scorer or StockScorer()
        self._advisor = advisor or EntryExitAdvisor()
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._notification_manager = notification_manager

    def generate_report(
        self,
        stock_scores: list[StockScore],
        recommendations: list[TradeRecommendation],
        market_summary: Optional[dict] = None,
        position_checks: Optional[list[dict]] = None,
    ) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        lines = []
        lines.append(f"# A股智能推荐日报 - {date_str}")
        lines.append("")

        if market_summary:
            lines.append("## 市场概览")
            lines.append("")
            for key, value in market_summary.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        top_stocks = sorted(stock_scores, key=lambda x: x.total_score, reverse=True)[:10]
        if top_stocks:
            lines.append("## Top 10 推荐股票")
            lines.append("")
            lines.append("| 排名 | 代码 | 名称 | 综合评分 | 评级 | 技术面 | 基本面 | 资金面 | 情绪面 |")
            lines.append("|------|------|------|----------|------|--------|--------|--------|--------|")
            for s in top_stocks:
                lines.append(
                    f"| {s.rank} | {s.symbol} | {s.name} | {s.total_score:.1f} | "
                    f"{s.rating.value} | {s.technical_score:.1f} | {s.fundamental_score:.1f} | "
                    f"{s.capital_score:.1f} | {s.sentiment_score:.1f} |"
                )
            lines.append("")

        buy_recs = [r for r in recommendations if r.recommendation_type.value == "买入"]
        if buy_recs:
            lines.append("## 买入推荐")
            lines.append("")
            for rec in buy_recs:
                lines.append(f"### {rec.symbol} {rec.name}")
                lines.append(f"- **当前价格**: {rec.current_price:.2f}")
                lines.append(f"- **建议买入区间**: {rec.entry_price_low:.2f} ~ {rec.entry_price_high:.2f}")
                lines.append(f"- **止损价**: {rec.stop_loss:.2f}")
                lines.append(f"- **止盈价**: {rec.take_profit:.2f}")
                lines.append(f"- **建议仓位**: {rec.position_pct:.0%}")
                lines.append(f"- **置信度**: {rec.confidence:.0%}")
                if rec.reasons:
                    lines.append(f"- **推荐理由**: {'; '.join(rec.reasons)}")
                if rec.risk_warnings:
                    lines.append(f"- **风险提示**: {'; '.join(rec.risk_warnings)}")
                lines.append("")

        if position_checks:
            lines.append("## 持仓检查")
            lines.append("")
            for pos in position_checks:
                symbol = pos.get("symbol", "")
                status = pos.get("status", "")
                lines.append(f"- **{symbol}**: {status}")
            lines.append("")

        content = "\n".join(lines)

        report_path = self._output_dir / f"daily_{date_str}.md"
        report_path.write_text(content, encoding="utf-8")
        logger.info("Daily report saved to %s", report_path)

        self._push_notifications(recommendations, stock_scores)

        return content

    def _push_notifications(
        self,
        recommendations: list[TradeRecommendation],
        stock_scores: list[StockScore],
    ) -> None:
        if not self._notification_manager:
            return

        from trading_system.notification.channels import NotificationLevel, NotificationMessage

        strong_buys = [r for r in recommendations if r.recommendation_type.value == "买入" and r.score and r.score.rating.value == "强推"]
        for rec in strong_buys:
            msg = NotificationMessage(
                title=f"强推股票: {rec.symbol} {rec.name}",
                content=f"综合评分: {rec.score.total_score:.1f}\n"
                        f"买入区间: {rec.entry_price_low:.2f}~{rec.entry_price_high:.2f}\n"
                        f"止损: {rec.stop_loss:.2f} 止盈: {rec.take_profit:.2f}\n"
                        f"推荐理由: {'; '.join(rec.reasons[:3])}",
                level=NotificationLevel.CRITICAL,
                source="推荐系统",
            )
            self._notification_manager.notify(msg)

        if recommendations:
            buy_count = sum(1 for r in recommendations if r.recommendation_type.value == "买入")
            top3 = sorted(stock_scores, key=lambda x: x.total_score, reverse=True)[:3]
            summary = f"今日推荐{buy_count}只买入\n"
            summary += "\n".join(f"  {s.symbol} {s.name}: {s.total_score:.1f}({s.rating.value})" for s in top3)
            msg = NotificationMessage(
                title="每日推荐报告",
                content=summary,
                level=NotificationLevel.INFO,
                source="推荐系统",
            )
            self._notification_manager.notify(msg)

    def push_urgent_notification(self, title: str, content: str) -> None:
        if not self._notification_manager:
            return
        from trading_system.notification.channels import NotificationLevel, NotificationMessage
        msg = NotificationMessage(
            title=title,
            content=content,
            level=NotificationLevel.CRITICAL,
            source="推荐系统",
        )
        self._notification_manager.notify(msg)

    def generate_rich_output(
        self,
        stock_scores: list[StockScore],
        recommendations: list[TradeRecommendation],
        market_summary: Optional[dict] = None,
    ) -> None:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            console = Console()

            if market_summary:
                summary_text = "\n".join(f"  {k}: {v}" for k, v in market_summary.items())
                console.print(Panel(summary_text, title="市场概览", border_style="cyan"))

            if stock_scores:
                table = Table(title="Top 10 推荐")
                table.add_column("排名", width=4)
                table.add_column("代码", width=8)
                table.add_column("名称", width=10)
                table.add_column("综合评分", width=8)
                table.add_column("评级", width=6)

                for s in sorted(stock_scores, key=lambda x: x.total_score, reverse=True)[:10]:
                    table.add_row(
                        str(s.rank), s.symbol, s.name,
                        f"{s.total_score:.1f}", s.rating.value,
                    )
                console.print(table)

        except ImportError:
            logger.warning("Rich library not available for terminal output")
