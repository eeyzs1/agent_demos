import logging
from datetime import datetime, timedelta

from trading_system.risk.manager import RiskManager

logger = logging.getLogger(__name__)


def generate_weekly_report(
    risk_manager: RiskManager,
    initial_capital: float,
    output_dir: str = "./output/reports",
) -> str:
    from pathlib import Path

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    state = risk_manager.get_state()
    closed_trades = risk_manager.get_closed_trades()

    week_ago = datetime.now() - timedelta(days=7)
    week_trades = [
        t
        for t in closed_trades
        if datetime.fromisoformat(t.get("exit_time", "2000-01-01")) >= week_ago
    ]

    week_pnl = sum(t.get("pnl", 0) for t in week_trades)
    week_win = [t for t in week_trades if t.get("pnl", 0) > 0]
    week_loss = [t for t in week_trades if t.get("pnl", 0) <= 0]
    week_win_pnl = sum(t.get("pnl", 0) for t in week_win)
    week_loss_pnl = sum(abs(t.get("pnl", 0)) for t in week_loss)

    reason_breakdown: dict[str, int] = {}
    for t in week_trades:
        reason = t.get("reason", "unknown")
        reason_breakdown[reason] = reason_breakdown.get(reason, 0) + 1

    strategy_breakdown: dict[str, dict] = {}
    for t in week_trades:
        strat = t.get("strategy", "unknown")
        if strat not in strategy_breakdown:
            strategy_breakdown[strat] = {"count": 0, "pnl": 0.0, "wins": 0}
        strategy_breakdown[strat]["count"] += 1
        strategy_breakdown[strat]["pnl"] += t.get("pnl", 0)
        if t.get("pnl", 0) > 0:
            strategy_breakdown[strat]["wins"] += 1

    avg_r = (
        sum(t.get("r_multiple", 0) for t in week_trades) / len(week_trades) if week_trades else 0
    )
    avg_hold = (
        sum(t.get("holding_days", 0) for t in week_trades) / len(week_trades) if week_trades else 0
    )

    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# 周报 - {week_start} ~ {week_end}",
        "",
        "## 账户总览",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 当前权益 | {state.equity:,.2f} |",
        f"| 初始资金 | {initial_capital:,.2f} |",
        f"| 累计收益率 | {(state.equity - initial_capital) / initial_capital * 100:.2f}% |",
        f"| 当前回撤 | {state.current_drawdown * 100:.2f}% |",
        f"| 波动率乘数 | {state.vol_multiplier:.4f} |",
        f"| 回撤乘数 | {state.drawdown_multiplier:.4f} |",
        f"| 总交易次数 | {state.total_trades} |",
        "",
        "## 本周绩效",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 本周盈亏 | {week_pnl:,.2f} |",
        f"| 本周交易 | {len(week_trades)} 笔 |",
        f"| 胜率 | {len(week_win) / len(week_trades) * 100:.1f}% |"
        if week_trades
        else "| 胜率 | N/A |",
        f"| 盈利因子 | {week_win_pnl / week_loss_pnl:.2f} |"
        if week_loss_pnl > 0
        else "| 盈利因子 | ∞ |",
        f"| 平均R倍数 | {avg_r:.2f}R |",
        f"| 平均持仓天数 | {avg_hold:.1f} |",
        "",
        "## 平仓原因分布",
        "",
    ]

    for reason, count in reason_breakdown.items():
        lines.append(f"- {reason}: {count} 笔")

    lines.extend(["", "## 策略表现", ""])

    if strategy_breakdown:
        lines.append("| 策略 | 交易数 | 盈利数 | 盈亏 | 胜率 |")
        lines.append("|------|--------|--------|------|------|")
        for strat, data in strategy_breakdown.items():
            wr = data["wins"] / data["count"] * 100 if data["count"] > 0 else 0
            lines.append(
                f"| {strat} | {data['count']} | {data['wins']} | {data['pnl']:.2f} | {wr:.1f}% |"
            )
    else:
        lines.append("本周无策略交易")

    lines.extend(
        [
            "",
            "## 风控状态",
            "",
            f"- 熔断状态: {'🚨 已触发' if state.is_circuit_breaker_active else '✅ 正常'}",
            f"- 连亏次数: {state.consecutive_losses}",
            f"- 回撤去风险乘数: {state.drawdown_multiplier:.4f}",
            f"- 波动率目标乘数: {state.vol_multiplier:.4f}",
        ]
    )

    if state.current_drawdown > 0.10:
        lines.append("")
        lines.append("⚠️ **回撤已超过10%，风控系统已开始渐进降仓**")

    if state.current_drawdown > 0.15:
        lines.append("🚨 **回撤超过15%，建议审查策略是否适应当前行情**")

    report_text = "\n".join(lines)

    date_str = datetime.now().strftime("%Y-W%W")
    report_path = output_path / f"weekly_{date_str}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info("Weekly report saved to %s", report_path)
    return report_text
