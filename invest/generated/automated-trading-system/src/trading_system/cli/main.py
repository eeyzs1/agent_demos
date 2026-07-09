"""CLI entry point — Click commands with Rich terminal UI.

Architecture rule AR008: presentation only, no business logic.
All commands delegate to domain modules.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from ..core.config import get_config

console = Console()
logger = logging.getLogger(__name__)

# Output format constants
FMT_JSON = "json"
FMT_TABLE = "table"
FMT_MD = "markdown"


def _fmt_output(data: Any, fmt: str, title: str = "") -> None:
    """Render output in the requested format."""
    if fmt == FMT_JSON:
        if isinstance(data, pd.DataFrame):
            console.print_json(data.to_json(orient="records", force_ascii=False))
        else:
            console.print_json(json.dumps(data, ensure_ascii=False, default=str))
    elif fmt == FMT_MD:
        if isinstance(data, pd.DataFrame):
            console.print(data.to_markdown(index=False))
        elif isinstance(data, dict):
            _print_dict_md(data, title)
        elif isinstance(data, list):
            for item in data:
                console.print(f"- {item}")
        else:
            console.print(str(data))
    else:  # table
        if isinstance(data, pd.DataFrame):
            _print_df_table(data, title)
        elif isinstance(data, dict):
            _print_dict_table(data, title)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            _print_list_table(data, title)
        else:
            console.print(data)


def _print_df_table(df: pd.DataFrame, title: str) -> None:
    """Print DataFrame as a Rich table."""
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    for col in df.columns[:12]:
        table.add_column(str(col), style="green" if "score" in str(col).lower() else "")
    for _, row in df.head(50).iterrows():
        table.add_row(*[str(row[c])[:20] for c in df.columns[:12]])
    if len(df) > 50:
        table.caption = f"... and {len(df) - 50} more rows"
    console.print(table)


def _print_dict_table(data: dict, title: str) -> None:
    """Print a dict as a 2-column table."""
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Key", style="dim")
    table.add_column("Value", style="green")
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False, default=str)[:80]
        table.add_row(str(k), str(v)[:80])
    console.print(table)


def _print_list_table(items: list, title: str) -> None:
    """Print a list of dicts as a Rich table."""
    if not items:
        console.print("[dim](empty)[/dim]")
        return
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    for key in items[0].keys():
        table.add_column(str(key))
    for item in items[:50]:
        table.add_row(*[str(item.get(k, ""))[:30] for k in items[0].keys()])
    if len(items) > 50:
        table.caption = f"... and {len(items) - 50} more items"
    console.print(table)


def _print_dict_md(data: dict, title: str) -> None:
    """Print a dict as Markdown."""
    if title:
        console.print(f"\n## {title}\n")
    for k, v in data.items():
        if isinstance(v, dict):
            console.print(f"**{k}**:")
            for sk, sv in v.items():
                console.print(f"  - {sk}: {sv}")
        elif isinstance(v, list):
            console.print(f"**{k}**: {', '.join(str(x) for x in v[:5])}")
        else:
            console.print(f"**{k}**: {v}")


def _progress_bar() -> Progress:
    """Create a standard progress bar."""
    return Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    )


# ======================================================================
# CLI Group
# ======================================================================

@click.group()
@click.option("--config-dir", default="config", help="Configuration directory")
@click.option("--output", "-o", type=click.Choice([FMT_TABLE, FMT_JSON, FMT_MD]),
              default=FMT_TABLE, help="Output format")
@click.pass_context
def cli(ctx, config_dir, output):
    """Automated Trading System — CLI for screening, strategy, backtest, execution.

    All commands produce structured output. Use --output to choose format.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_dir"] = config_dir
    ctx.obj["output"] = output


# ======================================================================
# Data Commands
# ======================================================================

@cli.group()
def data():
    """Market data operations."""


@data.command("fetch")
@click.argument("symbol", default="000300")
@click.option("--start", default="20240101", help="Start date YYYYMMDD")
@click.option("--end", default=None, help="End date YYYYMMDD")
@click.pass_context
def data_fetch(ctx, symbol, start, end):
    """Fetch daily OHLCV data for a stock or index."""
    from ..data.fetcher import MarketDataFetcher
    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    df = fetcher.get_daily_data(symbol, start, end)
    if df is None or df.empty:
        console.print(f"[red]No data found for {symbol}[/red]")
        return
    _fmt_output(df.tail(20), ctx.obj["output"], f"Daily Data: {symbol}")


@data.command("list")
@click.pass_context
def data_list(ctx):
    """List all A-share stocks."""
    from ..data.fetcher import MarketDataFetcher
    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    df = fetcher.get_stock_list()
    if df is None or df.empty:
        console.print("[red]Failed to fetch stock list[/red]")
        return
    _fmt_output(df.head(100), ctx.obj["output"], f"Stock List ({len(df)} total)")


# ======================================================================
# Screener Commands
# ======================================================================

@cli.group()
def screener():
    """Stock screening and multi-factor scoring."""


@screener.command("score")
@click.argument("symbol")
@click.option("--start", default="20240101", help="Start date")
@click.option("--end", default=None, help="End date")
@click.pass_context
def screener_score(ctx, symbol, start, end):
    """Score a single stock across all factors."""
    from ..pipeline.screener import StockScreener
    s = StockScreener(ctx.obj["config_dir"])
    with _progress_bar() as progress:
        task = progress.add_task(f"Scoring {symbol}...", total=1)
        result = s.score_stock(symbol)
        progress.update(task, advance=1)
    _fmt_output(result, ctx.obj["output"], f"Factor Scores: {symbol}")


@screener.command("screen")
@click.option("--top", "-n", default=20, help="Top N candidates")
@click.option("--start", default="20240101", help="Start date")
@click.option("--end", default=None, help="End date")
@click.pass_context
def screener_screen(ctx, top, start, end):
    """Run full market screen and return top candidates."""
    from ..pipeline.screener import StockScreener
    from ..data.fetcher import MarketDataFetcher
    s = StockScreener(ctx.obj["config_dir"])
    fetcher = MarketDataFetcher(ctx.obj["config_dir"])

    with _progress_bar() as progress:
        task = progress.add_task("Fetching stock list...", total=3)
        stock_list = fetcher.get_stock_list()
        progress.update(task, advance=1, description="Screening...")
        df = s.screen(stock_list, start, end)
        progress.update(task, advance=1, description="Ranking...")
        if df is not None and not df.empty:
            top_df = s.get_top_candidates(df, top)
        else:
            top_df = pd.DataFrame()
        progress.update(task, advance=1)

    if top_df.empty:
        console.print("[yellow]No candidates found[/yellow]")
        return
    _fmt_output(top_df, ctx.obj["output"], f"Top {top} Candidates")


# ======================================================================
# Strategy Commands
# ======================================================================

@cli.group()
def strategy():
    """Strategy engine and signal generation."""


@strategy.command("signals")
@click.argument("symbol")
@click.option("--start", default="20240101", help="Start date")
@click.option("--end", default=None, help="End date")
@click.pass_context
def strategy_signals(ctx, symbol, start, end):
    """Generate trading signals for a stock."""
    from ..strategy.strategies import StrategyEngine
    from ..data.fetcher import MarketDataFetcher
    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    engine = StrategyEngine(ctx.obj["config_dir"])

    with _progress_bar() as progress:
        task = progress.add_task(f"Generating signals for {symbol}...", total=2)
        df = fetcher.get_daily_data(symbol, start, end)
        progress.update(task, advance=1)
        if df is None or df.empty:
            console.print(f"[red]No data for {symbol}[/red]")
            return
        signals = engine.generate_signals({symbol: df})
        progress.update(task, advance=1)

    if signals.empty:
        console.print("[yellow]No signals generated[/yellow]")
        return
    _fmt_output(signals.tail(20), ctx.obj["output"], f"Signals: {symbol}")


@strategy.command("weights")
@click.pass_context
def strategy_weights(ctx):
    """Show current strategy fusion weights."""
    cfg = get_config(ctx.obj["config_dir"])
    weights = cfg.get("strategy.weights", {})
    _fmt_output(weights, ctx.obj["output"], "Strategy Weights")


# ======================================================================
# Backtest Commands
# ======================================================================

@cli.group()
def backtest():
    """Backtest engine and analysis."""


@backtest.command("run")
@click.argument("symbol")
@click.option("--start", default="20200101", help="Start date")
@click.option("--end", default=None, help="End date")
@click.option("--capital", default=100000.0, help="Initial capital")
@click.option("--mc", is_flag=True, help="Run Monte Carlo simulation")
@click.pass_context
def backtest_run(ctx, symbol, start, end, capital, mc):
    """Run a backtest for a stock."""
    from ..backtest.engine import BacktestEngine
    from ..strategy.strategies import StrategyEngine
    from ..data.fetcher import MarketDataFetcher

    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    engine = StrategyEngine(ctx.obj["config_dir"])
    bt = BacktestEngine(ctx.obj["config_dir"])

    with _progress_bar() as progress:
        task = progress.add_task(f"Backtesting {symbol}...", total=4)
        df = fetcher.get_daily_data(symbol, start, end)
        progress.update(task, advance=1)
        if df is None or df.empty:
            console.print(f"[red]No data for {symbol}[/red]")
            return
        signals = engine.generate_signals({symbol: df})
        progress.update(task, advance=1)
        metrics, trades = bt.run_backtest(df, signals, initial_capital=capital)
        progress.update(task, advance=1)

        mc_result = None
        if mc:
            mc_result = bt.run_monte_carlo()
        progress.update(task, advance=1)

    # Print metrics
    m = metrics
    metrics_dict = {
        "total_trades": m.total_trades,
        "win_rate": f"{m.win_rate * 100:.1f}%",
        "risk_reward_ratio": f"{m.risk_reward_ratio:.2f}",
        "max_drawdown": f"{m.max_drawdown * 100:.1f}%",
        "annual_return": f"{m.annual_return * 100:.1f}%",
        "sharpe_ratio": f"{m.sharpe_ratio:.2f}",
        "max_consecutive_losses": m.max_consecutive_losses,
        "avg_r_multiple": f"{m.avg_r_multiple:.2f}",
    }
    _fmt_output(metrics_dict, ctx.obj["output"], f"Backtest: {symbol}")

    if mc_result:
        console.print()
        mc_dict = {
            "p10": f"{mc_result.p10:.1f}", "p25": f"{mc_result.p25:.1f}",
            "p50": f"{mc_result.p50:.1f}", "p75": f"{mc_result.p75:.1f}",
            "p90": f"{mc_result.p90:.1f}", "loss_probability": f"{mc_result.loss_probability * 100:.1f}%",
        }
        _fmt_output(mc_dict, ctx.obj["output"], "Monte Carlo Results")


@backtest.command("dsr")
@click.argument("symbol")
@click.option("--start", default="20200101", help="Start date")
@click.option("--end", default=None, help="End date")
@click.option("--capital", default=100000.0, help="Initial capital")
@click.pass_context
def backtest_dsr(ctx, symbol, start, end, capital):
    """Calculate Deflated Sharpe Ratio for a stock."""
    from ..backtest.engine import BacktestEngine
    from ..strategy.strategies import StrategyEngine
    from ..data.fetcher import MarketDataFetcher

    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    engine = StrategyEngine(ctx.obj["config_dir"])
    bt = BacktestEngine(ctx.obj["config_dir"])

    with _progress_bar() as progress:
        task = progress.add_task(f"Computing DSR for {symbol}...", total=3)
        df = fetcher.get_daily_data(symbol, start, end)
        progress.update(task, advance=1)
        signals = engine.generate_signals({symbol: df})
        progress.update(task, advance=1)
        bt.run_backtest(df, signals, initial_capital=capital)
        dsr = bt.calculate_deflated_sharpe()
        progress.update(task, advance=1)

    _fmt_output(dsr, ctx.obj["output"], f"Deflated Sharpe Ratio: {symbol}")


# ======================================================================
# Risk Commands
# ======================================================================

@cli.group()
def risk():
    """Risk management and controls."""


@risk.command("status")
@click.pass_context
def risk_status(ctx):
    """Show current risk management state."""
    from ..risk.manager import RiskManager
    rm = RiskManager(ctx.obj["config_dir"])
    state = rm.get_state()
    _fmt_output(state, ctx.obj["output"], "Risk State")


@risk.command("check")
@click.argument("symbol")
@click.option("--price", type=float, required=True, help="Position price")
@click.option("--quantity", type=int, required=True, help="Position quantity")
@click.option("--direction", type=click.Choice(["long", "short"]), default="long")
@click.pass_context
def risk_check(ctx, symbol, price, quantity, direction):
    """Check if a position can be opened."""
    from ..risk.manager import RiskManager
    rm = RiskManager(ctx.obj["config_dir"])
    ok, reason = rm.can_open_position(symbol, price, quantity, direction)
    result = {"allowed": ok, "reason": reason}
    if ok:
        console.print(f"[green]✓ {reason}[/green]")
    else:
        console.print(f"[red]✗ {reason}[/red]")
    _fmt_output(result, ctx.obj["output"], f"Risk Check: {symbol}")


# ======================================================================
# Execution Commands
# ======================================================================

@cli.group()
def trade():
    """Trade execution (paper trading default)."""


@trade.command("paper")
@click.argument("symbol")
@click.option("--action", type=click.Choice(["buy", "sell"]), required=True)
@click.option("--quantity", type=int, required=True)
@click.option("--price", type=float, default=None, help="Limit price (market order if None)")
@click.pass_context
def trade_paper(ctx, symbol, action, quantity, price):
    """Submit a paper trade order."""
    from ..execution.executor import PaperExecutor
    executor = PaperExecutor(ctx.obj["config_dir"])
    order = executor.submit_order(symbol, action, quantity, price)
    label = "[green]✓[/green]" if order.get("status") == "filled" else "[yellow]⟳[/yellow]"
    console.print(f"{label} Order: {order}")
    _fmt_output(order, ctx.obj["output"], f"Paper Order: {symbol}")


@trade.command("orders")
@click.pass_context
def trade_orders(ctx):
    """List all orders."""
    from ..execution.executor import PaperExecutor
    executor = PaperExecutor(ctx.obj["config_dir"])
    orders = executor.get_orders()
    if not orders:
        console.print("[dim]No orders yet[/dim]")
        return
    _fmt_output(orders, ctx.obj["output"], "Order History")


@trade.command("positions")
@click.pass_context
def trade_positions(ctx):
    """List current positions."""
    from ..execution.executor import PaperExecutor
    executor = PaperExecutor(ctx.obj["config_dir"])
    positions = executor.get_positions()
    if not positions:
        console.print("[dim]No open positions[/dim]")
        return
    _fmt_output(positions, ctx.obj["output"], "Current Positions")


# ======================================================================
# Sentiment Commands
# ======================================================================

@cli.group()
def sentiment():
    """Market sentiment analysis."""


@sentiment.command("analyze")
@click.option("--index", default="000300", help="Index code")
@click.pass_context
def sentiment_analyze(ctx, index):
    """Run 6-dimension sentiment analysis."""
    from ..sentiment.analyzer import SentimentAnalyzer
    analyzer = SentimentAnalyzer(ctx.obj["config_dir"])
    with _progress_bar() as progress:
        task = progress.add_task("Analyzing sentiment...", total=1)
        result = analyzer.analyze()
        progress.update(task, advance=1)

    # Color-code the level
    level = result.get("level", "")
    color = {"极度乐观": "green", "偏乐观": "bright_green", "中性": "yellow",
             "偏悲观": "bright_red", "极度悲观": "red"}.get(level, "white")
    console.print(Panel(f"[bold {color}]{level}[/bold {color}] (score: {result.get('score', 0)}/{result.get('momentum', '')})",
                        title="Market Sentiment"))
    _fmt_output(result, ctx.obj["output"], "Sentiment Analysis")


@sentiment.command("hotspots")
@click.pass_context
def sentiment_hotspots(ctx):
    """Show market hotspot sectors."""
    from ..sentiment.analyzer import SentimentAnalyzer
    analyzer = SentimentAnalyzer(ctx.obj["config_dir"])
    result = analyzer.analyze()
    hotspots = result.get("hotspots", [])
    if not hotspots:
        console.print("[dim]No hotspot data[/dim]")
        return
    _fmt_output(hotspots, ctx.obj["output"], "Market Hotspots")


# ======================================================================
# Research Commands
# ======================================================================

@cli.group()
def research():
    """Fundamental research analysis."""


@research.command("analyze")
@click.argument("symbol")
@click.pass_context
def research_analyze(ctx, symbol):
    """Run full fundamental analysis on a stock."""
    from ..research.analyzer import ResearchAnalyzer
    ra = ResearchAnalyzer(ctx.obj["config_dir"])
    with _progress_bar() as progress:
        task = progress.add_task(f"Analyzing {symbol}...", total=1)
        result = ra.analyze(symbol)
        progress.update(task, advance=1)

    score = result.get("overall_score", 0.5)
    color = "green" if score > 0.6 else "yellow" if score > 0.4 else "red"
    console.print(Panel(f"[bold {color}]Score: {score:.2f}[/bold {color}]",
                        title=f"Research: {symbol}"))

    findings = result.get("key_findings", [])
    if findings:
        console.print("\n[bold]Key Findings:[/bold]")
        for f in findings:
            console.print(f"  • {f}")

    warnings = result.get("risk_warnings", [])
    if warnings:
        console.print("\n[bold red]Risk Warnings:[/bold red]")
        for w in warnings:
            console.print(f"  ⚠ {w}")

    _fmt_output(result, ctx.obj["output"], f"Research: {symbol}")


@research.command("announcements")
@click.argument("symbol")
@click.option("--days", type=int, default=30, help="Lookback days")
@click.pass_context
def research_announcements(ctx, symbol, days):
    """Scan recent announcements for a stock."""
    from ..research.analyzer import ResearchAnalyzer
    ra = ResearchAnalyzer(ctx.obj["config_dir"])
    announcements = ra.scan_announcements(symbol, days)
    if not announcements:
        console.print(f"[dim]No announcements found for {symbol} in last {days} days[/dim]")
        return
    _fmt_output(announcements, ctx.obj["output"], f"Announcements: {symbol}")


# ======================================================================
# Portfolio Commands
# ======================================================================

@cli.group()
def portfolio():
    """Portfolio optimization."""


@portfolio.command("optimize")
@click.option("--symbols", "-s", multiple=True, required=True, help="Stock symbols")
@click.option("--method", type=click.Choice(["markowitz", "risk_parity", "hrp"]),
              default="markowitz", help="Optimization method")
@click.option("--start", default="20230101", help="Start date")
@click.option("--end", default=None, help="End date")
@click.pass_context
def portfolio_optimize(ctx, symbols, method, start, end):
    """Optimize a portfolio of stocks."""
    from ..portfolio.optimizer import PortfolioOptimizer
    from ..data.fetcher import MarketDataFetcher

    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    optimizer = PortfolioOptimizer(ctx.obj["config_dir"])

    with _progress_bar() as progress:
        task = progress.add_task("Fetching data...", total=len(symbols) + 2)
        prices = {}
        for sym in symbols:
            df = fetcher.get_daily_data(sym, start, end)
            if df is not None and not df.empty and "close" in df.columns:
                prices[sym] = df.set_index("date")["close"]
            progress.update(task, advance=1)

        if len(prices) < 2:
            console.print("[red]Need at least 2 stocks with valid data[/red]")
            return

        price_df = pd.DataFrame(prices).dropna()
        returns_df = price_df.pct_change().dropna()
        progress.update(task, advance=1, description="Optimizing...")

        weights = optimizer.optimize(returns_df, method=method)
        progress.update(task, advance=1)

    _fmt_output(weights, ctx.obj["output"], f"Portfolio Weights ({method})")


# ======================================================================
# Arbitrage Commands
# ======================================================================

@cli.group()
def arb():
    """Statistical arbitrage."""


@arb.command("pairs")
@click.option("--symbols", "-s", multiple=True, help="Stock symbols to search")
@click.option("--min-corr", type=float, default=0.5, help="Minimum correlation")
@click.option("--max-pairs", type=int, default=10, help="Max pairs to return")
@click.option("--start", default="20220101", help="Start date")
@click.pass_context
def arb_pairs(ctx, symbols, min_corr, max_pairs, start):
    """Discover cointegrated pairs."""
    from ..ml.arbitrage import StatArbEngine
    from ..data.fetcher import MarketDataFetcher

    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    engine = StatArbEngine(ctx.obj["config_dir"])

    syms = list(symbols) if symbols else None
    if not syms:
        stock_list = fetcher.get_stock_list()
        syms = stock_list["code"].head(50).tolist() if stock_list is not None else []

    with _progress_bar() as progress:
        task = progress.add_task("Fetching price data...", total=len(syms) + 2)
        prices = {}
        for sym in syms:
            df = fetcher.get_daily_data(sym, start)
            if df is not None and not df.empty and "close" in df.columns:
                prices[sym] = df.set_index("date")["close"]
            progress.update(task, advance=1)

        price_df = pd.DataFrame(prices).dropna()
        progress.update(task, advance=1, description="Finding pairs...")
        pairs = engine.find_pairs(price_df, min_correlation=min_corr, max_pairs=max_pairs)
        progress.update(task, advance=1)

    if not pairs:
        console.print("[yellow]No cointegrated pairs found[/yellow]")
        return
    _fmt_output([{"ticker1": p[0], "ticker2": p[1], "half_life": f"{p[2]:.1f}",
                   "hedge_ratio": f"{p[3]:.4f}"} for p in pairs],
                ctx.obj["output"], "Cointegrated Pairs")


@arb.command("regime")
@click.argument("symbol")
@click.option("--start", default="20220101", help="Start date")
@click.pass_context
def arb_regime(ctx, symbol, start):
    """Detect market regime for a stock."""
    from ..ml.arbitrage import StatArbEngine
    from ..data.fetcher import MarketDataFetcher

    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    engine = StatArbEngine(ctx.obj["config_dir"])

    df = fetcher.get_daily_data(symbol, start)
    if df is None or df.empty:
        console.print(f"[red]No data for {symbol}[/red]")
        return

    returns = df.set_index("date")["close"].pct_change().dropna()
    result = engine.get_regime(returns)

    # Show regime distribution
    regime_counts = result["regime"].value_counts().to_dict()
    current = result["regime"].iloc[-1]
    color = "green" if current == "bullish" else "red" if current == "bearish" else "yellow"
    console.print(Panel(f"[bold {color}]{current}[/bold {color}]\nSignal: {result['signal'].iloc[-1]}",
                        title=f"Regime: {symbol}"))
    _fmt_output(regime_counts, ctx.obj["output"], f"Regime Distribution: {symbol}")


# ======================================================================
# Pipeline Commands
# ======================================================================

@cli.command("daily-run")
@click.option("--top", "-n", default=20, help="Top N candidates")
@click.option("--start", default="20240101", help="Start date")
@click.pass_context
def daily_run(ctx, top, start):
    """Run complete daily pipeline: scan → score → strategy → risk → report."""
    from ..pipeline.screener import StockScreener
    from ..strategy.strategies import StrategyEngine
    from ..risk.manager import RiskManager
    from ..sentiment.analyzer import SentimentAnalyzer
    from ..data.fetcher import MarketDataFetcher

    cfg = get_config(ctx.obj["config_dir"])
    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    screener = StockScreener(ctx.obj["config_dir"])
    engine = StrategyEngine(ctx.obj["config_dir"])
    risk_mgr = RiskManager(ctx.obj["config_dir"])
    sentiment = SentimentAnalyzer(ctx.obj["config_dir"])

    console.print(Panel.fit("[bold blue]Daily Pipeline Run[/bold blue]", border_style="blue"))
    start_time = datetime.now()

    with _progress_bar() as progress:
        # Step 1: Market sentiment
        task = progress.add_task("Market sentiment...", total=6)
        sent = sentiment.analyze()
        progress.update(task, advance=1)

        # Step 2: Stock list
        progress.update(task, description="Fetching stock list...")
        stock_list = fetcher.get_stock_list()
        progress.update(task, advance=1)

        # Step 3: Screen
        progress.update(task, description="Screening stocks...")
        candidates = screener.screen(stock_list, start, None)
        if candidates is None or candidates.empty:
            console.print("[red]Screening returned no candidates[/red]")
            return
        top_candidates = screener.get_top_candidates(candidates, top)
        progress.update(task, advance=1)

        # Step 4: Strategy signals
        progress.update(task, description="Generating signals...")
        stock_data = {}
        for _, row in top_candidates.iterrows():
            code = row["code"]
            df = fetcher.get_daily_data(code, start)
            if df is not None and not df.empty:
                stock_data[code] = df
        signals = engine.generate_signals(stock_data)
        progress.update(task, advance=1)

        # Step 5: Risk assessment
        progress.update(task, description="Risk assessment...")
        risk_state = risk_mgr.get_state()
        progress.update(task, advance=1)

        # Step 6: Report
        progress.update(task, description="Generating report...")
        progress.update(task, advance=1)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Print report
    console.print()
    console.print(Panel.fit("[bold green]Daily Report[/bold green]", border_style="green"))

    # Sentiment summary
    console.print(f"\n[bold]Market Sentiment:[/bold] {sent.get('level', 'N/A')} "
                  f"(score: {sent.get('score', 0)}, momentum: {sent.get('momentum', 'N/A')})")

    # Top candidates
    console.print(f"\n[bold]Top {top} Candidates:[/bold]")
    if not top_candidates.empty:
        display_cols = [c for c in ["code", "name", "total", "technical", "fundamental"] if c in top_candidates.columns]
        _print_df_table(top_candidates[display_cols].head(10), "Top Candidates")

    # Risk status
    circuit = risk_state.get("circuit_breaker_active", False)
    if circuit:
        console.print(f"\n[bold red]⚠ Circuit Breaker Active:[/bold red] {risk_state.get('circuit_breaker_reason', 'Unknown')}")
    else:
        console.print(f"\n[bold green]Risk Status:[/bold green] Normal")

    console.print(f"\n[dim]Pipeline completed in {elapsed:.1f}s[/dim]")


@cli.command("daily-trade")
@click.option("--top", "-n", default=10, help="Top N candidates")
@click.option("--start", default="20240101", help="Start date")
@click.pass_context
def daily_trade(ctx, top, start):
    """Run complete daily trading pipeline: scan → score → fusion → risk → order."""
    from ..pipeline.screener import StockScreener
    from ..strategy.strategies import StrategyEngine
    from ..risk.manager import RiskManager
    from ..execution.executor import PaperExecutor
    from ..data.fetcher import MarketDataFetcher

    cfg = get_config(ctx.obj["config_dir"])
    fetcher = MarketDataFetcher(ctx.obj["config_dir"])
    screener = StockScreener(ctx.obj["config_dir"])
    engine = StrategyEngine(ctx.obj["config_dir"])
    risk_mgr = RiskManager(ctx.obj["config_dir"])
    executor = PaperExecutor(ctx.obj["config_dir"])

    console.print(Panel.fit("[bold yellow]Daily Trading Pipeline[/bold yellow]", border_style="yellow"))

    with _progress_bar() as progress:
        task = progress.add_task("Running pipeline...", total=5)
        stock_list = fetcher.get_stock_list()
        progress.update(task, advance=1)

        candidates = screener.screen(stock_list, start, None)
        if candidates is None or candidates.empty:
            console.print("[red]No candidates[/red]")
            return
        top_candidates = screener.get_top_candidates(candidates, top)
        progress.update(task, advance=1)

        stock_data = {}
        for _, row in top_candidates.iterrows():
            code = row["code"]
            df = fetcher.get_daily_data(code, start)
            if df is not None and not df.empty:
                stock_data[code] = df
        signals = engine.generate_signals(stock_data)
        progress.update(task, advance=1)

        orders = []
        if not signals.empty:
            latest = signals.groupby("symbol").last().reset_index()
            for _, row in latest.iterrows():
                sym = row["symbol"]
                cs = row.get("combined_score", 0)
                if cs > 0.3:
                    ok, reason = risk_mgr.can_open_position(sym, 10.0, 100, "long")
                    if ok:
                        order = executor.submit_order(sym, "buy", 100)
                        orders.append(order)
                    else:
                        orders.append({"symbol": sym, "status": "rejected", "reason": reason})
        progress.update(task, advance=1, description="Generating report...")
        progress.update(task, advance=1)

    console.print(f"\n[bold]Orders:[/bold] {len(orders)} submitted")
    if orders:
        _fmt_output(orders, ctx.obj["output"], "Trade Orders")


# ======================================================================
# Main Entry Point
# ======================================================================

def main():
    """Entry point for the trading system CLI."""
    cli(auto_envvar_prefix="TRADE")


if __name__ == "__main__":
    main()