import logging
from datetime import datetime

from trading_system.risk.manager import RiskManager

logger = logging.getLogger(__name__)


def generate_daily_report(
    risk_manager: RiskManager,
    initial_capital: float,
    output_dir: str = "./output/reports",
) -> str:
    from pathlib import Path

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    state = risk_manager.get_state()
    positions = risk_manager.positions
    closed_trades = risk_manager.get_closed_trades()

    today_trades = [
        t
        for t in closed_trades
        if t.get("exit_time", "").startswith(datetime.now().strftime("%Y-%m-%d"))
    ]

    today_pnl = sum(t.get("pnl", 0) for t in today_trades)
    today_win = sum(1 for t in today_trades if t.get("pnl", 0) > 0)
    today_loss = sum(1 for t in today_trades if t.get("pnl", 0) <= 0)

    lines = [
        f"# 日报 - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## 账户概览",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 当前权益 | {state.equity:,.2f} |",
        f"| 初始资金 | {initial_capital:,.2f} |",
        f"| 累计收益率 | {(state.equity - initial_capital) / initial_capital * 100:.2f}% |",
        f"| 当前回撤 | {state.current_drawdown * 100:.2f}% |",
        f"| 波动率乘数 | {state.vol_multiplier:.4f} |",
        f"| 回撤乘数 | {state.drawdown_multiplier:.4f} |",
        f"| 熔断状态 | {'🚨 已触发' if state.is_circuit_breaker_active else '✅ 正常'} |",
        f"| 连亏次数 | {state.consecutive_losses} |",
        "",
        "## 持仓明细",
        "",
    ]

    if positions:
        lines.append("| 标的 | 方向 | 数量 | 入场价 | 止损 | 追踪止损 | 持仓天数 |")
        lines.append("|------|------|------|--------|------|----------|----------|")
        for sym, pos in positions.items():
            trail_str = f"{pos.trailing_stop:.2f}" if pos.trailing_stop else "—"
            lines.append(
                f"| {sym} | {pos.side} | {pos.quantity:.0f} | {pos.entry_price:.2f} "
                f"| {pos.stop_loss:.2f} | {trail_str} | {pos.holding_days} |"
            )
    else:
        lines.append("当前无持仓")

    lines.extend(
        [
            "",
            "## 今日交易",
            "",
        ]
    )

    if today_trades:
        lines.append("| 标的 | 方向 | 盈亏 | R倍数 | 原因 |")
        lines.append("|------|------|------|-------|------|")
        for t in today_trades:
            lines.append(
                f"| {t.get('symbol', '')} | {t.get('side', '')} "
                f"| {t.get('pnl', 0):.2f} | {t.get('r_multiple', 0):.2f}R "
                f"| {t.get('reason', '')} |"
            )
    else:
        lines.append("今日无交易")

    lines.extend(
        [
            "",
            "## 今日汇总",
            "",
            f"- 今日盈亏: {today_pnl:,.2f}",
            f"- 今日交易: {len(today_trades)} 笔 (盈利 {today_win} / 亏损 {today_loss})",
            f"- 日内亏损: {abs(state.daily_loss):,.2f}",
        ]
    )

    report_text = "\n".join(lines)

    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = output_path / f"daily_{date_str}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info("Daily report saved to %s", report_path)
    return report_text
