import csv
import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading_system.backtest.engine import BacktestResult

logger = logging.getLogger(__name__)
console = Console()


def format_pct(value: float) -> str:
    if value >= 0:
        return f"[green]+{value:.2f}%[/green]"
    return f"[red]{value:.2f}%[/red]"


def format_number(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


def display_backtest_result(
    result: BacktestResult, initial_capital: float, symbol: str = ""
) -> None:
    summary = result.summary(initial_capital)
    metrics = summary["seven_key_metrics"]

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]回测报告[/bold cyan]  {symbol}",
            border_style="cyan",
        )
    )

    metrics_table = Table(title="7大关键量化指标", show_header=True, header_style="bold magenta")
    metrics_table.add_column("指标", style="cyan", width=24)
    metrics_table.add_column("数值", style="bold", width=16)
    metrics_table.add_column("评估", width=20)

    wr = metrics["win_rate"]
    wr_eval = "✅ 优秀" if wr >= 0.5 else "⚠️ 可接受" if wr >= 0.35 else "❌ 需改进"
    metrics_table.add_row("胜率 (Win Rate)", f"{wr:.1%}", wr_eval)

    rr = metrics["risk_reward_ratio"]
    rr_eval = "✅ 优秀" if rr >= 2.0 else "⚠️ 可接受" if rr >= 1.5 else "❌ 需改进"
    metrics_table.add_row("风险/回报比 (R/R)", f"1:{rr:.2f}", rr_eval)

    mdd = metrics["max_drawdown"]
    mdd_eval = "✅ 安全" if mdd <= 0.15 else "⚠️ 注意" if mdd <= 0.25 else "❌ 危险"
    metrics_table.add_row("最大回撤 (Max DD)", f"{mdd:.1%}", mdd_eval)

    rpt = metrics["risk_per_trade_pct"]
    rpt_eval = "✅ 合理" if rpt <= 0.02 else "⚠️ 偏高" if rpt <= 0.05 else "❌ 过高"
    metrics_table.add_row("每笔风险百分比", f"{rpt:.1%}", rpt_eval)

    ar = metrics["annualized_return"]
    ar_eval = "✅ 优秀" if ar >= 0.3 else "⚠️ 一般" if ar >= 0.15 else "❌ 不足"
    metrics_table.add_row("年化收益率", f"{ar:.1%}", ar_eval)

    mcl = metrics["max_consecutive_losses"]
    mcl_eval = "✅ 可承受" if mcl <= 5 else "⚠️ 需准备" if mcl <= 10 else "❌ 风险高"
    metrics_table.add_row("最大连亏次数", str(mcl), mcl_eval)

    arm = metrics["avg_r_multiple"]
    arm_eval = "✅ 大赚小赔" if arm >= 1.5 else "⚠️ 一般" if arm >= 0.5 else "❌ 小赚大赔"
    metrics_table.add_row("平均R倍数", f"{arm:.2f}R", arm_eval)

    console.print(metrics_table)

    perf_table = Table(title="绩效概览", show_header=True, header_style="bold blue")
    perf_table.add_column("指标", style="cyan", width=20)
    perf_table.add_column("数值", style="bold", width=16)

    perf_table.add_row("总交易次数", str(summary["total_trades"]))
    perf_table.add_row("盈利次数", str(summary["winning_trades"]))
    perf_table.add_row("亏损次数", str(summary["losing_trades"]))
    perf_table.add_row("总盈亏", format_number(summary["total_pnl"]))
    perf_table.add_row("总收益率", format_pct(summary["total_return_pct"]))
    perf_table.add_row("年化收益率", format_pct(summary["annualized_return_pct"]))
    perf_table.add_row("夏普比率", f"{summary['sharpe_ratio']:.2f}")
    perf_table.add_row("盈利因子", f"{summary['profit_factor']:.2f}")
    perf_table.add_row("平均盈利", format_pct(summary["avg_win_pct"]))
    perf_table.add_row("平均亏损", format_pct(summary["avg_loss_pct"]))
    perf_table.add_row("最终权益", format_number(summary["final_equity"]))

    console.print(perf_table)

    if result.trades:
        trade_table = Table(
            title="最近交易记录", show_header=True, header_style="bold yellow", max_rows=20
        )
        trade_table.add_column("日期", width=12)
        trade_table.add_column("方向", width=6)
        trade_table.add_column("入场", width=10)
        trade_table.add_column("出场", width=10)
        trade_table.add_column("盈亏", width=12)
        trade_table.add_column("R倍数", width=8)
        trade_table.add_column("原因", width=12)

        for t in result.trades[-20:]:
            pnl_str = format_pct(t.pnl_pct)
            r_str = f"{t.r_multiple:.2f}R"
            date_str = (
                t.exit_date.strftime("%Y-%m-%d")
                if hasattr(t.exit_date, "strftime")
                else str(t.exit_date)[:10]
            )
            trade_table.add_row(
                date_str,
                t.side,
                format_number(t.entry_price),
                format_number(t.exit_price),
                pnl_str,
                r_str,
                t.exit_reason,
            )

        console.print(trade_table)

    console.print()


def save_equity_curve_csv(result: BacktestResult, output_dir: str = "./output") -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "equity_curve.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["date", "equity", "position_value", "drawdown", "vol_multiplier", "dd_multiplier"]
        )
        for i in range(len(result.equity_curve)):
            date_str = (
                result.dates[i].strftime("%Y-%m-%d")
                if hasattr(result.dates[i], "strftime")
                else str(result.dates[i])[:10]
            )
            pos_val = result.position_sizes[i] if i < len(result.position_sizes) else 0
            dd = result.drawdown_curve[i] if i < len(result.drawdown_curve) else 0
            vol_m = result.vol_multipliers[i] if i < len(result.vol_multipliers) else 1.0
            dd_m = result.dd_multipliers[i] if i < len(result.dd_multipliers) else 1.0
            writer.writerow(
                [
                    date_str,
                    f"{result.equity_curve[i]:.2f}",
                    f"{pos_val:.2f}",
                    f"{dd:.4f}",
                    f"{vol_m:.4f}",
                    f"{dd_m:.4f}",
                ]
            )

    logger.info("Equity curve saved to %s", csv_path)
    return csv_path


def save_report_md(
    result: BacktestResult, initial_capital: float, symbol: str = "", output_dir: str = "./output"
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    md_path = output_path / "report.md"

    summary = result.summary(initial_capital)
    metrics = summary["seven_key_metrics"]
    breakdown = summary.get("exit_reason_breakdown", {})

    lines = [
        f"# 回测报告 - {symbol}",
        "",
        "## 7大关键量化指标",
        "",
        "| 指标 | 数值 | 评估 |",
        "|------|------|------|",
    ]

    evaluations = {
        "win_rate": (0.5, 0.35),
        "risk_reward_ratio": (2.0, 1.5),
        "max_drawdown": (0.15, 0.25),
        "risk_per_trade_pct": (0.02, 0.05),
        "annualized_return": (0.3, 0.15),
        "avg_r_multiple": (1.5, 0.5),
    }

    metric_labels = {
        "win_rate": "胜率",
        "risk_reward_ratio": "风险/回报比",
        "max_drawdown": "最大回撤",
        "risk_per_trade_pct": "每笔风险%",
        "annualized_return": "年化收益率",
        "max_consecutive_losses": "最大连亏",
        "avg_r_multiple": "平均R倍数",
    }

    for key, label in metric_labels.items():
        val = metrics[key]
        if key == "max_consecutive_losses":
            ev = "✅" if val <= 5 else "⚠️" if val <= 10 else "❌"
            lines.append(f"| {label} | {val} | {ev} |")
        elif key in evaluations:
            good, ok = evaluations[key]
            if key == "max_drawdown" or key == "risk_per_trade_pct":
                ev = "✅" if val <= good else "⚠️" if val <= ok else "❌"
            else:
                ev = "✅" if val >= good else "⚠️" if val >= ok else "❌"
            lines.append(f"| {label} | {val:.4f} | {ev} |")

    lines.extend(
        [
            "",
            "## 绩效概览",
            "",
            f"- 总交易次数: {summary['total_trades']}",
            f"- 盈利次数: {summary['winning_trades']}",
            f"- 亏损次数: {summary['losing_trades']}",
            f"- 总盈亏: {summary['total_pnl']:.2f}",
            f"- 总收益率: {summary['total_return_pct']:.2f}%",
            f"- 年化收益率: {summary['annualized_return_pct']:.2f}%",
            f"- 夏普比率: {summary['sharpe_ratio']:.4f}",
            f"- 盈利因子: {summary['profit_factor']:.4f}",
            f"- 平均盈利: {summary['avg_win_pct']:.2f}%",
            f"- 平均亏损: {summary['avg_loss_pct']:.2f}%",
            f"- 最终权益: {summary['final_equity']:.2f}",
            f"- 平均持仓天数: {summary.get('avg_holding_days', 'N/A')}",
        ]
    )

    if breakdown:
        lines.extend(["", "## 平仓原因分布", ""])
        for reason, count in breakdown.items():
            lines.append(f"- {reason}: {count}")

    lines.extend(["", "## 交易记录", ""])
    lines.append("| 入场日期 | 方向 | 入场价 | 出场价 | 盈亏% | R倍数 | 原因 | 持仓天数 |")
    lines.append("|----------|------|--------|--------|-------|-------|------|----------|")
    for t in result.trades:
        entry_str = (
            t.entry_date.strftime("%Y-%m-%d")
            if hasattr(t.entry_date, "strftime")
            else str(t.entry_date)[:10]
        )
        lines.append(
            f"| {entry_str} | {t.side} | {t.entry_price:.2f} | {t.exit_price:.2f} "
            f"| {t.pnl_pct:.2f}% | {t.r_multiple:.2f}R | {t.exit_reason} | {t.holding_days} |"
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Report saved to %s", md_path)
    return md_path


def save_equity_curve_png(
    result: BacktestResult, initial_capital: float, symbol: str = "", output_dir: str = "./output"
) -> Optional[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed, skipping PNG output")
        return None

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    png_path = output_path / "equity_curve.png"

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1, 1]})

    ax1 = axes[0]
    dates = result.dates
    ax1.plot(dates, result.equity_curve, label="净值曲线", color="steelblue", linewidth=1.5)
    ax1.axhline(y=initial_capital, color="gray", linestyle="--", alpha=0.5, label="初始资金")
    ax1.set_title(f"回测净值曲线 - {symbol}", fontsize=14)
    ax1.set_ylabel("权益")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    if result.drawdown_curve:
        ax2.fill_between(dates, result.drawdown_curve, alpha=0.4, color="red", label="回撤")
        ax2.set_ylabel("回撤")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

    ax3 = axes[2]
    if result.vol_multipliers:
        ax3.plot(dates, result.vol_multipliers, label="波动率乘数", color="orange", linewidth=1)
        ax3.plot(dates, result.dd_multipliers, label="回撤乘数", color="purple", linewidth=1)
        ax3.set_ylabel("风控乘数")
        ax3.set_xlabel("日期")
        ax3.legend()
        ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    logger.info("Equity curve chart saved to %s", png_path)
    return png_path


def generate_optimization_suggestions(result: BacktestResult, initial_capital: float) -> list[str]:
    suggestions = []
    summary = result.summary(initial_capital)
    metrics = summary["seven_key_metrics"]
    breakdown = summary.get("exit_reason_breakdown", {})

    if metrics["win_rate"] < 0.35:
        suggestions.append(
            "胜率过低（<35%）：建议收紧入场条件，增加确认信号，或考虑换用均值回归类策略"
        )

    if metrics["max_drawdown"] > 0.25:
        suggestions.append(
            "最大回撤过大（>25%）：建议降低 drawdown_soft_limit（当前回撤去风险阈值），"
            "或减小 max_risk_per_trade"
        )

    if metrics["risk_reward_ratio"] < 1.5:
        suggestions.append(
            "风险回报比不足（<1.5:1）：建议放宽止盈目标（增大 default_take_profit_rr），"
            "或收紧止损（减小 ATR 乘数）"
        )

    if metrics["avg_r_multiple"] < 0.5:
        suggestions.append(
            "平均R倍数过低（<0.5R）：盈亏比不佳，大亏小赚。建议检查止损是否过宽，或止盈是否过窄"
        )

    if metrics["max_consecutive_losses"] > 8:
        suggestions.append(
            "最大连亏次数过多（>8）：策略可能在某些行情下持续失效，"
            "建议增加市场状态过滤，或降低 max_consecutive_losses 触发更早停"
        )

    if breakdown.get("timeout", 0) > breakdown.get("take_profit", 0):
        suggestions.append(
            "超时平仓次数多于止盈次数：持仓时间不足以致胜，"
            "建议增大 max_holding_days，或调整策略参数使信号更及时"
        )

    if breakdown.get("trailing_stop", 0) > 0 and breakdown.get("stop_loss", 0) > breakdown.get(
        "trailing_stop", 0
    ):
        suggestions.append(
            "固定止损触发多于追踪止损：浮盈保护不足，"
            "建议降低 trailing_stop_activate_pct（更早激活追踪止损）"
        )

    if summary["sharpe_ratio"] < 0.5:
        suggestions.append(
            "夏普比率过低（<0.5）：风险调整后收益不佳，"
            "建议启用波动率目标仓位（降低 target_volatility）"
        )

    if not suggestions:
        suggestions.append("策略表现良好，暂无重大优化建议。可关注细节参数微调。")

    return suggestions


def save_optimization_suggestions(
    result: BacktestResult, initial_capital: float, output_dir: str = "./output"
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    sug_path = output_path / "optimization_suggestions.md"

    suggestions = generate_optimization_suggestions(result, initial_capital)

    lines = [
        "# 策略优化建议",
        "",
        "基于回测结果自动生成的优化建议：",
        "",
    ]
    for i, sug in enumerate(suggestions, 1):
        lines.append(f"{i}. {sug}")
        lines.append("")

    with open(sug_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Optimization suggestions saved to %s", sug_path)
    return sug_path


def save_all_outputs(
    result: BacktestResult, initial_capital: float, symbol: str = "", output_dir: str = "./output"
) -> dict[str, Path]:
    outputs = {}
    outputs["csv"] = save_equity_curve_csv(result, output_dir)
    outputs["md"] = save_report_md(result, initial_capital, symbol, output_dir)
    outputs["suggestions"] = save_optimization_suggestions(result, initial_capital, output_dir)

    png_path = save_equity_curve_png(result, initial_capital, symbol, output_dir)
    if png_path:
        outputs["png"] = png_path

    return outputs
