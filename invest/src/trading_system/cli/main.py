import logging
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading_system.analysis.market import MarketAnalyzer
from trading_system.backtest.engine import BacktestEngine
from trading_system.backtest.montecarlo import ProbabilisticBacktestEngine
from trading_system.backtest.report import display_backtest_result
from trading_system.backtest.significance import StrategySignificanceTester
from trading_system.core.config import AppConfig
from trading_system.core.logging_config import setup_logging
from trading_system.data.intraday import VolumeProfile
from trading_system.data.store import DataStore
from trading_system.data.watchlist import WatchlistManager
from trading_system.execution.engine import TradingEngine
from trading_system.execution.impact import MarketImpactModel
from trading_system.execution.scheduler import ExecutionScheduler
from trading_system.execution.tca import TransactionCostAnalyzer
from trading_system.ml.hmm_regime import HMMRegimeDetector
from trading_system.ml.kalman_filter import KalmanHedgeRatio
from trading_system.ml.microstructure import OrderBookSignalExtractor
from trading_system.ml.volatility import VolatilityForecaster
from trading_system.portfolio.covariance import CovarianceEstimator
from trading_system.portfolio.factor_model import FactorModel
from trading_system.portfolio.optimizer import PortfolioOptimizer
from trading_system.portfolio.risk_parity import HRPOptimizer, RiskParityOptimizer
from trading_system.research.engine import ResearchEngine
from trading_system.research.sources import ResearchDataAggregator
from trading_system.sentiment.analyzer import MarketSentimentAnalyzer, SentimentLevel
from trading_system.sentiment.hotspot import HotSpotDetector
from trading_system.strategy.pairs_trading import PairsRegistry, PairsTradingStrategy
from trading_system.strategy.strategies import STRATEGY_REGISTRY, create_strategy, list_strategies

console = Console()


def load_config() -> AppConfig:
    config_path = Path("./config/default.yaml")
    return AppConfig.from_yaml(config_path)


@click.group()
@click.option("--config", "-c", default="./config/default.yaml", help="配置文件路径")
@click.option("--log-level", default="INFO", help="日志级别 (DEBUG/INFO/WARNING/ERROR)")
@click.pass_context
def cli(ctx, config, log_level):
    """🚀 自动化交易系统 - 投研、策略、回测、执行"""
    setup_logging(level=log_level)
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["config"] = AppConfig.from_yaml(config)


@cli.group()
def data():
    """📊 数据管理：获取行情、管理缓存"""
    pass


@data.command("fetch")
@click.argument("symbol")
@click.option("--source", "-s", default="akshare", help="数据源 (akshare/yfinance)")
@click.option("--start", "-st", default=None, help="开始日期 (YYYYMMDD)")
@click.option("--end", "-et", default=None, help="结束日期 (YYYYMMDD)")
@click.option("--save", "-sv", is_flag=True, help="保存到CSV")
@click.pass_context
def fetch_data(ctx, symbol, source, start, end, save):
    """获取股票日线数据"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    console.print(f"[cyan]正在获取 {symbol} 日线数据...[/cyan]")
    try:
        df = store.fetch_daily(symbol, source=source, start_date=start, end_date=end)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        console.print(f"[green]成功获取 {len(df)} 条记录[/green]")

        table = Table(title=f"{symbol} 日线数据")
        table.add_column("日期", style="cyan")
        table.add_column("开盘", style="white")
        table.add_column("最高", style="green")
        table.add_column("最低", style="red")
        table.add_column("收盘", style="yellow")
        table.add_column("成交量", style="white")

        for idx, row in df.tail(20).iterrows():
            table.add_row(
                str(idx)[:10] if hasattr(idx, "strftime") else str(idx)[:10],
                f"{row.get('open', 0):.2f}",
                f"{row.get('high', 0):.2f}",
                f"{row.get('low', 0):.2f}",
                f"{row.get('close', 0):.2f}",
                f"{row.get('volume', 0):,.0f}",
            )

        console.print(table)

        if save:
            save_path = Path(f"./data/{symbol}_daily.csv")
            save_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(save_path)
            console.print(f"[green]数据已保存到 {save_path}[/green]")

    except Exception as e:
        console.print(f"[red]获取数据失败: {e}[/red]")


@data.command("analyze")
@click.argument("symbol")
@click.option("--source", "-s", default="akshare", help="数据源")
@click.pass_context
def analyze_data(ctx, symbol, source):
    """分析股票技术指标和市场状态"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    console.print(f"[cyan]正在分析 {symbol}...[/cyan]")
    try:
        df = store.fetch_daily(symbol, source=source)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        result = MarketAnalyzer.analyze_symbol(df)

        state_colors = {"BULL": "green", "BEAR": "red", "RANGE": "yellow", "UNKNOWN": "white"}
        state = result.get("market_state", "UNKNOWN")
        color = state_colors.get(state, "white")

        console.print(
            Panel.fit(
                f"[bold]市场状态:[/bold] [{color}]{state}[/{color}]\n"
                f"[bold]当前价格:[/bold] {result.get('current_price', 'N/A')}\n"
                f"[bold]RSI(14):[/bold] {result.get('rsi', 'N/A')}\n"
                f"[bold]MACD:[/bold] {result.get('macd', 'N/A')}\n"
                f"[bold]ATR(14):[/bold] {result.get('atr', 'N/A')}\n"
                f"[bold]ADX(14):[/bold] {result.get('adx', 'N/A')}\n"
                f"[bold]量比:[/bold] {result.get('volume_ratio', 'N/A')}\n"
                f"[bold]布林上轨:[/bold] {result.get('bb_upper', 'N/A')}\n"
                f"[bold]布林下轨:[/bold] {result.get('bb_lower', 'N/A')}\n"
                f"[bold]技术信号:[/bold] {', '.join(result.get('signals', []))}",
                title=f"📊 {symbol} 分析",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]分析失败: {e}[/red]")


@data.command("intraday")
@click.argument("symbol")
@click.option("--period", "-p", default="30min", help="K线周期 (5/15/30/60)")
@click.option("--days", "-d", default=5, help="获取天数")
@click.pass_context
def fetch_intraday_data(ctx, symbol, period, days):
    """获取日内K线数据"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    console.print(f"[cyan]正在获取 {symbol} {period} K线数据...[/cyan]")
    try:
        df = store.fetch_intraday(symbol, period=period.replace("min", ""), days_back=days)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        console.print(f"[green]成功获取 {len(df)} 条记录[/green]")

        table = Table(title=f"{symbol} {period} K线 (最近{len(df.tail(20))}条)")
        table.add_column("时间", style="cyan")
        table.add_column("开盘", style="white")
        table.add_column("收盘", style="yellow")
        table.add_column("最高", style="green")
        table.add_column("最低", style="red")
        table.add_column("成交量", style="white")

        for idx, row in df.tail(20).iterrows():
            table.add_row(
                str(idx)[:19],
                f"{row.get('open', 0):.2f}",
                f"{row.get('close', 0):.2f}",
                f"{row.get('high', 0):.2f}",
                f"{row.get('low', 0):.2f}",
                f"{row.get('volume', 0):,.0f}",
            )
        console.print(table)

    except Exception as e:
        console.print(f"[red]获取日内数据失败: {e}[/red]")


@cli.group()
def watchlist():
    """📋 观察列表管理"""
    pass


@watchlist.command("create")
@click.argument("name")
@click.option("--auto-fetch", is_flag=True, help="自动获取数据")
@click.pass_context
def create_watchlist(ctx, name, auto_fetch):
    """创建新的观察列表"""
    config = ctx.obj["config"]
    manager = WatchlistManager(data_dir=str(Path(config.data.cache_dir).parent))
    try:
        wl = manager.create(name, auto_fetch=auto_fetch)
        console.print(f"[green]观察列表 '{wl.name}' 创建成功[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")


@watchlist.command("add")
@click.argument("watchlist_name")
@click.argument("symbol")
@click.option("--name", "-n", default="", help="股票名称")
@click.pass_context
def add_to_watchlist(ctx, watchlist_name, symbol, name):
    """向观察列表添加股票"""
    config = ctx.obj["config"]
    manager = WatchlistManager(data_dir=str(Path(config.data.cache_dir).parent))
    try:
        manager.add_symbol(watchlist_name, symbol, name)
        console.print(f"[green]{symbol} 已添加到 '{watchlist_name}'[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")


@watchlist.command("list")
@click.pass_context
def list_watchlists(ctx):
    """列出所有观察列表"""
    config = ctx.obj["config"]
    manager = WatchlistManager(data_dir=str(Path(config.data.cache_dir).parent))
    watchlists = manager.list_all()

    if not watchlists:
        console.print("[yellow]暂无观察列表[/yellow]")
        return

    table = Table(title="观察列表")
    table.add_column("名称", style="cyan")
    table.add_column("股票数", style="green")
    table.add_column("自动获取", style="yellow")

    for wl in watchlists:
        table.add_row(wl.name, str(len(wl.symbols)), "✓" if wl.auto_fetch else "✗")

    console.print(table)


@cli.group()
def strategy():
    """🎯 策略管理：查看、回测策略"""
    pass


@strategy.command("list")
def list_strategies_cmd():
    """列出所有可用策略"""
    strategies = list_strategies()

    table = Table(title="可用策略")
    table.add_column("名称", style="cyan")
    table.add_column("类型", style="green")
    table.add_column("描述", style="white")
    table.add_column("适合市场", style="yellow")

    for s in strategies:
        table.add_row(
            s["name"],
            s["type"],
            s["description"],
            ", ".join(s["suitable_markets"]),
        )

    console.print(table)


@strategy.command("backtest")
@click.argument("strategy_name")
@click.argument("symbol")
@click.option("--source", "-s", default="akshare", help="数据源")
@click.option("--start", "-st", default=None, help="开始日期")
@click.option("--end", "-et", default=None, help="结束日期")
@click.option("--capital", "-cap", default=100000.0, help="初始资金")
@click.option("--params", "-p", default=None, help="策略参数 (JSON格式)")
@click.pass_context
def backtest_strategy(ctx, strategy_name, symbol, source, start, end, capital, params):
    """回测指定策略"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    if strategy_name not in STRATEGY_REGISTRY:
        console.print(f"[red]未知策略: {strategy_name}[/red]")
        console.print(f"[yellow]可用策略: {', '.join(STRATEGY_REGISTRY.keys())}[/yellow]")
        return

    strategy_params = None
    if params:
        import json

        try:
            strategy_params = json.loads(params)
        except json.JSONDecodeError:
            console.print("[red]参数JSON格式错误[/red]")
            return

    strat = create_strategy(strategy_name, strategy_params)

    console.print(f"[cyan]正在获取 {symbol} 数据...[/cyan]")
    try:
        df = store.fetch_daily(symbol, source=source, start_date=start, end_date=end)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return
    except Exception as e:
        console.print(f"[red]获取数据失败: {e}[/red]")
        return

    console.print(f"[cyan]正在回测 {strategy_name} 策略...[/cyan]")
    engine = BacktestEngine(
        strategy=strat,
        initial_capital=capital,
        risk_config=config.risk,
    )

    result = engine.run(df, symbol=symbol)
    display_backtest_result(result, capital, symbol)


@cli.group()
def sentiment():
    """🌡️ 市场情绪：情绪分析、热点捕捉、持续性分析"""
    pass


@sentiment.command("analyze")
@click.option("--symbol", "-s", default=None, help="指定指数代码（如000001）")
@click.pass_context
def analyze_sentiment(ctx, symbol):
    """分析市场情绪指标"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)
    analyzer = MarketSentimentAnalyzer()

    console.print("[cyan]正在分析市场情绪...[/cyan]")
    try:
        index_code = symbol or "000001"
        df = store.fetch_daily(index_code, source="akshare", use_cache=True)
        if df.empty:
            console.print("[red]未获取到指数数据[/red]")
            return

        result = analyzer.analyze_from_index_data(df)
        level_colors = {
            SentimentLevel.EXTREME_FEAR: "red",
            SentimentLevel.FEAR: "orange3",
            SentimentLevel.NEUTRAL: "yellow",
            SentimentLevel.GREED: "green",
            SentimentLevel.EXTREME_GREED: "bold red",
        }
        level_names = {
            SentimentLevel.EXTREME_FEAR: "极度恐惧 😱",
            SentimentLevel.FEAR: "恐惧 😟",
            SentimentLevel.NEUTRAL: "中性 😐",
            SentimentLevel.GREED: "贪婪 😊",
            SentimentLevel.EXTREME_GREED: "极度贪婪 🤑",
        }
        color = level_colors.get(result.level, "white")
        name = level_names.get(result.level, result.level.value)

        trend = analyzer.get_trend()

        console.print(
            Panel.fit(
                f"[bold]情绪评分:[/bold] [{color}]{result.score:.0f}/100[/{color}]\n"
                f"[bold]情绪等级:[/bold] [{color}]{name}[/{color}]\n"
                f"[bold]趋势方向:[/bold] {trend.get('direction', 'N/A')}\n"
                f"[bold]趋势变化:[/bold] {trend.get('change', 0):+.1f}\n"
                f"[bold]分项得分:[/bold]\n"
                + "\n".join(f"  · {k}: {v:.1f}" for k, v in result.components.items()),
                title="🌡️ 市场情绪分析",
                border_style=color,
            )
        )

    except Exception as e:
        console.print(f"[red]情绪分析失败: {e}[/red]")


@sentiment.command("hotspot")
@click.option("--top", "-t", default=10, help="显示前N个热点")
@click.pass_context
def detect_hotspots(ctx, top):
    """捕捉市场热点板块"""
    console.print("[cyan]正在检测市场热点...[/cyan]")
    try:
        detector = HotSpotDetector()
        aggregator = ResearchDataAggregator()

        sector_data = aggregator.fetch_sector_data()
        if sector_data.empty:
            console.print("[red]未获取到板块数据[/red]")
            return

        spots = detector.detect_hot_spots(sector_data, top_n=top)

        if not spots:
            console.print("[yellow]暂无热点[/yellow]")
            return

        table = Table(title="🔥 市场热点")
        table.add_column("排名", style="white", width=4)
        table.add_column("板块", style="cyan", width=12)
        table.add_column("热度", style="bold", width=6)
        table.add_column("涨跌幅", width=8)
        table.add_column("量比", width=6)
        table.add_column("持续天数", width=8)
        table.add_column("持续性", width=8)
        table.add_column("动量", width=10)

        momentum_colors = {
            "climax": "bold red",
            "strengthening": "green",
            "continuing": "yellow",
            "emerging": "cyan",
            "weakening": "orange3",
            "fading": "dim",
        }

        for i, spot in enumerate(spots, 1):
            change_str = f"{spot.avg_change_pct:+.2f}%"
            mom_color = momentum_colors.get(spot.momentum, "white")
            table.add_row(
                str(i),
                spot.name,
                f"{spot.score:.0f}",
                change_str,
                f"{spot.volume_ratio:.1f}",
                str(spot.consecutive_days),
                f"{spot.persistence_score:.0f}",
                f"[{mom_color}]{spot.momentum}[/{mom_color}]",
            )

        console.print(table)

        concept_data = aggregator.fetch_concept_sectors()
        if not concept_data.empty:
            concept_spots = detector.detect_hot_spots(concept_data, top_n=5)
            if concept_spots:
                ctable = Table(title="💡 概念热点")
                ctable.add_column("概念", style="cyan")
                ctable.add_column("热度", style="bold")
                ctable.add_column("涨跌幅")
                ctable.add_column("动量")

                for s in concept_spots:
                    ctable.add_row(
                        s.name,
                        f"{s.score:.0f}",
                        f"{s.avg_change_pct:+.2f}%",
                        s.momentum,
                    )
                console.print(ctable)

    except Exception as e:
        console.print(f"[red]热点检测失败: {e}[/red]")


@sentiment.command("persistence")
@click.argument("spot_name")
@click.pass_context
def check_persistence(ctx, spot_name):
    """分析热点持续性"""
    console.print(f"[cyan]正在分析 '{spot_name}' 的持续性...[/cyan]")
    try:
        detector = HotSpotDetector()
        result = detector.analyze_persistence(spot_name)

        console.print(
            Panel.fit(
                f"[bold]热点名称:[/bold] {spot_name}\n"
                f"[bold]连续天数:[/bold] {result['consecutive_days']}\n"
                f"[bold]持续性评分:[/bold] {result['score']:.0f}/100\n"
                f"[bold]首次出现:[/bold] {result.get('first_seen', 'N/A')}\n"
                f"[bold]最近出现:[/bold] {result.get('last_seen', 'N/A')}",
                title="📈 热点持续性分析",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]分析失败: {e}[/red]")


@cli.group()
def research():
    """🔍 投研分析：新闻、研报、公告、资金流向"""
    pass


@research.command("symbol")
@click.argument("symbol")
@click.pass_context
def research_symbol(ctx, symbol):
    """对指定股票进行投研分析"""
    console.print(f"[cyan]正在对 {symbol} 进行投研分析...[/cyan]")
    try:
        engine = ResearchEngine()
        summary = engine.research_symbol(symbol)

        sentiment_colors = {"positive": "green", "negative": "red", "neutral": "yellow"}
        s_color = sentiment_colors.get(summary.news_sentiment, "white")

        console.print(
            Panel.fit(
                f"[bold]新闻情绪:[/bold] [{s_color}]{summary.news_sentiment}[/{s_color}]\n"
                f"[bold]新闻数量:[/bold] {summary.news_count}\n"
                f"[bold]关键发现:[/bold]\n"
                + "\n".join(f"  · {f}" for f in summary.key_findings)
                + (
                    "\n[bold]风险提示:[/bold]\n"
                    + "\n".join(f"  ⚠️ {w}" for w in summary.risk_warnings)
                    if summary.risk_warnings
                    else ""
                ),
                title=f"🔍 {symbol} 投研分析",
                border_style="cyan",
            )
        )

        if summary.top_news:
            ntable = Table(title="📰 最新新闻")
            ntable.add_column("标题", style="cyan", width=50)
            ntable.add_column("来源", width=10)
            ntable.add_column("时间", width=12)

            for n in summary.top_news[:5]:
                ntable.add_row(
                    n["title"][:50],
                    n["source"],
                    str(n.get("time", ""))[:10],
                )
            console.print(ntable)

        if summary.reports:
            rtable = Table(title="📋 研报")
            rtable.add_column("标题", style="cyan", width=40)
            rtable.add_column("机构", width=12)
            rtable.add_column("评级", width=8)

            for r in summary.reports[:5]:
                rtable.add_row(
                    r["title"][:40],
                    r.get("source", ""),
                    r.get("rating", ""),
                )
            console.print(rtable)

    except Exception as e:
        console.print(f"[red]投研分析失败: {e}[/red]")


@research.command("market")
@click.pass_context
def research_market(ctx):
    """全市场投研概览"""
    console.print("[cyan]正在生成市场投研概览...[/cyan]")
    try:
        engine = ResearchEngine()
        result = engine.research_market()

        hot_spots = result.get("hot_spots", [])
        if hot_spots:
            htable = Table(title="🔥 市场热点")
            htable.add_column("板块", style="cyan", width=12)
            htable.add_column("热度", style="bold", width=6)
            htable.add_column("涨跌幅", width=8)
            htable.add_column("持续天数", width=8)
            htable.add_column("持续性", width=8)
            htable.add_column("动量", width=10)

            for s in hot_spots[:10]:
                htable.add_row(
                    s["name"],
                    f"{s['score']:.0f}",
                    f"{s.get('change_pct', 0):+.2f}%",
                    str(s.get("consecutive_days", 1)),
                    f"{s.get('persistence_score', 0):.0f}",
                    s.get("momentum", ""),
                )
            console.print(htable)

        rotations = result.get("sector_rotations", [])
        if rotations:
            rtable = Table(title="🔄 板块轮动")
            rtable.add_column("排名", width=4)
            rtable.add_column("板块", style="cyan", width=12)
            rtable.add_column("评分", width=6)
            rtable.add_column("涨跌幅", width=8)
            rtable.add_column("资金流向", width=12)
            rtable.add_column("动量", width=10)

            for r in rotations[:10]:
                rtable.add_row(
                    str(r["rank"]),
                    r["sector"],
                    f"{r['score']:.0f}",
                    f"{r['change_pct']:+.2f}%",
                    f"{r['fund_flow']:,.0f}",
                    r["momentum"],
                )
            console.print(rtable)

        fund_inflow = result.get("top_fund_inflow", [])
        if fund_inflow:
            ftable = Table(title="💰 主力资金流入TOP5")
            ftable.add_column("代码", style="cyan")
            ftable.add_column("名称", style="white")
            ftable.add_column("净流入", style="green")

            for f in fund_inflow:
                ftable.add_row(
                    f["symbol"],
                    f["name"],
                    f"{f['net_inflow']:,.0f}",
                )
            console.print(ftable)

    except Exception as e:
        console.print(f"[red]市场分析失败: {e}[/red]")


@cli.group()
def trade():
    """💰 交易执行：纸上交易、实盘交易"""
    pass


@trade.command("status")
@click.pass_context
def trade_status(ctx):
    """查看交易系统状态"""
    config = ctx.obj["config"]
    engine = TradingEngine(config=config)
    status = engine.get_portfolio_status()

    state = status.copy()
    state["drawdown"] = f"{state['drawdown']:.2%}"
    state["circuit_breaker"] = "🔴 激活" if state["circuit_breaker"] else "🟢 正常"

    console.print(
        Panel.fit(
            f"[bold]交易模式:[/bold] {config.trading.mode}\n"
            f"[bold]初始资金:[/bold] {config.trading.initial_capital:,.2f}\n"
            f"[bold]现金余额:[/bold] {state['cash']:,.2f}\n"
            f"[bold]总权益:[/bold] {state['total_equity']:,.2f}\n"
            f"[bold]当前回撤:[/bold] {state['drawdown']}\n"
            f"[bold]连亏次数:[/bold] {state['consecutive_losses']}\n"
            f"[bold]熔断状态:[/bold] {state['circuit_breaker']}\n"
            f"[bold]总交易数:[/bold] {state['total_trades']}\n"
            f"[bold]持仓数:[/bold] {len(state['positions'])}",
            title="💰 交易系统状态",
            border_style="green",
        )
    )


@trade.command("start")
@click.option("--mode", "-m", type=click.Choice(["paper", "live"]), default="paper", help="交易模式")
@click.pass_context
def start_trading(ctx, mode):
    """启动交易引擎"""
    config = ctx.obj["config"]
    config.trading.mode = mode
    engine = TradingEngine(config=config)
    engine.start()
    ctx.obj["engine"] = engine
    console.print(f"[green]交易引擎已启动 (模式: {mode})[/green]")


@trade.command("stop")
@click.pass_context
def stop_trading(ctx):
    """停止交易引擎"""
    engine = ctx.obj.get("engine")
    if engine and engine.is_running:
        engine.stop()
        console.print("[yellow]交易引擎已停止[/yellow]")
    else:
        console.print("[dim]交易引擎未在运行[/dim]")


@trade.command("recommend")
@click.option("--top", "-t", default=10, help="推荐股票数量")
@click.option("--output", "-o", default="./output", help="报告输出目录")
@click.option("--candidates", "-n", default=100, help="候选股票数量 (50-500)")
@click.pass_context
def recommend_stocks(ctx, top, output, candidates):
    """生成每日推荐报告（全市场真实扫描）"""
    from trading_system.advisor.daily_report import DailyReportGenerator
    from trading_system.advisor.entry_exit import EntryExitAdvisor
    from trading_system.pipeline.scan_recommend import ScanRecommendPipeline
    from trading_system.scorer.engine import StockScorer

    console.print("[cyan]正在全市场扫描...[/cyan]")
    try:
        pipeline = ScanRecommendPipeline()
        stock_data_list, market_summary = pipeline.run(candidate_limit=candidates)

        if not stock_data_list:
            console.print("[red]未获取到有效股票数据，请检查网络或稍后重试[/red]")
            return

        console.print(f"[green]数据获取完成，共 {len(stock_data_list)} 只股票[/green]")
        console.print("[cyan]正在进行多因子评分...[/cyan]")

        scorer = StockScorer()
        scores = scorer.rank_stocks(stock_data_list)

        console.print("[cyan]正在生成推荐...[/cyan]")
        advisor = EntryExitAdvisor(scorer)
        generator = DailyReportGenerator(scorer=scorer, advisor=advisor, output_dir=output)

        recommendations = []
        for s in scores[:top]:
            price = s.details.get("price", 0)
            rec = advisor.recommend_entry(s.symbol, price, s.details)
            recommendations.append(rec)

        generator.generate_report(scores, recommendations, market_summary)

        from rich.table import Table
        table = Table(title=f"Top {min(top, len(scores))} 推荐股票")
        table.add_column("排名", style="bold", width=4)
        table.add_column("代码", width=8)
        table.add_column("名称", width=12)
        table.add_column("评分", width=6)
        table.add_column("评级", width=6)
        table.add_column("价格", width=8)

        for s in scores[:top]:
            price = s.details.get("price", 0)
            rating_style = {
                "强推": "[bold green]强推[/bold green]",
                "推荐": "[green]推荐[/green]",
                "观望": "[yellow]观望[/yellow]",
                "回避": "[red]回避[/red]",
            }.get(s.rating.value, s.rating.value)
            table.add_row(
                str(s.rank), s.symbol, s.name,
                f"{s.total_score:.1f}", rating_style,
                f"{price:.2f}" if price else "N/A",
            )

        console.print(table)
        console.print("[green]推荐报告已生成！[/green]")
        console.print(f"[cyan]报告路径: {output}[/cyan]")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("推荐报告生成失败")
        console.print(f"[red]推荐报告生成失败: {e}[/red]")


@trade.command("daily-run")
@click.option("--candidates", "-n", default=100, help="候选股票数量 (50-500)")
@click.option("--top", "-t", default=20, help="融合决策股票数量")
@click.option("--output", "-o", default="./output", help="报告输出目录")
@click.pass_context
def daily_run(ctx, candidates, top, output):
    """每日完整流程: 扫描→评分→策略融合→报告"""
    from trading_system.pipeline.daily_runner import DailyJobRunner

    console.print("[bold cyan]========== 每日自动化交易任务 ==========[/bold cyan]")
    start_time = datetime.now()

    try:
        runner = DailyJobRunner(output_dir=output)
        result = runner.run_daily(candidate_limit=candidates, top_n=top)

        if result["status"] == "failed":
            console.print(f"[red]任务失败: {result.get('error', 'unknown')}[/red]")
            return

        console.print()
        console.print(f"[bold green]========== 任务完成 (耗时 {result['elapsed_seconds']}秒) ==========[/bold green]")
        console.print(f"  扫描股票: {result['stocks_scanned']}只")
        console.print(f"  评分股票: {result['stocks_scored']}只")
        console.print(f"  融合决策: {result['fusion_decisions']}条")
        console.print(f"  买入信号: [green]{result['buy_count']}[/green]")
        console.print(f"  卖出信号: [red]{result['sell_count']}[/red]")
        console.print(f"  持有建议: [yellow]{result['hold_count']}[/yellow]")
        console.print()

        if result["top_buy"]:
            from rich.table import Table
            table = Table(title="Top 买入推荐（策略融合）")
            table.add_column("代码", width=10)
            table.add_column("名称", width=12)
            table.add_column("评分", width=6)
            table.add_column("融合置信度", width=10)
            table.add_column("策略共识", width=8)
            table.add_column("止损", width=8)
            table.add_column("止盈", width=8)

            for d in result["top_buy"]:
                consensus_style = {
                    "strong": "[bold green]强共识[/bold green]",
                    "moderate": "[green]中等[/green]",
                    "weak": "[yellow]弱[/yellow]",
                }.get(d.get("strategy_consensus", ""), d.get("strategy_consensus", "-"))
                table.add_row(
                    d["symbol"], d["name"],
                    f"{d['scorer_score']:.1f}",
                    f"{d['fusion_confidence']:.2%}",
                    consensus_style,
                    f"{d.get('stop_loss', 0):.2f}" if d.get("stop_loss") else "-",
                    f"{d.get('take_profit', 0):.2f}" if d.get("take_profit") else "-",
                )

            console.print(table)

        console.print(f"\n[cyan]报告目录: {output}[/cyan]")
        console.print(f"[cyan]交易信号: {result['signals_file']}[/cyan]")
        console.print(f"[cyan]每日汇总: {result['summary_file']}[/cyan]")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("每日任务失败")
        console.print(f"[red]每日任务失败: {e}[/red]")


@trade.command("daily-trade")
@click.option("--candidates", "-n", default=100, help="候选股票数量 (50-500)")
@click.option("--top", "-t", default=20, help="融合决策股票数量")
@click.option("--output", "-o", default="./output", help="输出目录")
@click.option("--dry-run/--live", default=True, help="模拟运行(默认) / 实际下单")
@click.pass_context
def daily_trade(ctx, candidates, top, output, dry_run):
    """每日自动交易: 扫描→评分→融合→风控→下单"""
    from trading_system.pipeline.trader import DailyTrader
    from rich.table import Table

    config = ctx.obj.get("config")
    mode_label = "[yellow]模拟运行 (DRY RUN)[/yellow]" if dry_run else "[bold red]实盘交易[/bold red]"
    console.print(f"[bold cyan]========== 每日自动交易 {mode_label} ==========[/bold cyan]")
    start_time = datetime.now()

    try:
        trader = DailyTrader(config=config, output_dir=output)
        report = trader.run(candidate_limit=candidates, top_n=top, dry_run=dry_run)

        console.print()
        portfolio = report["portfolio"]
        trade_sum = report["trade_summary"]

        console.print(f"[bold green]========== 交易完成 (耗时 {report['elapsed_seconds']}秒) ==========[/bold green]")
        console.print(f"  账户权益: {portfolio['total_equity']:,.0f}")
        console.print(f"  可用资金: {portfolio['cash']:,.0f}")
        console.print(f"  当前回撤: {portfolio['drawdown']:.2%}")
        console.print(f"  当前持仓: {portfolio['positions_count']}只")
        console.print(f"  熔断状态: {'[red]已触发[/red]' if portfolio['circuit_breaker'] else '[green]正常[/green]'}")
        console.print()
        console.print(f"  本次交易: 共 {trade_sum['total']} 笔")
        console.print(f"  已成交: [green]{trade_sum['filled']}[/green]")
        console.print(f"  已拒绝: [red]{trade_sum['rejected']}[/red]")
        console.print(f"  买入信号: {trade_sum['buy_signals']}")
        console.print(f"  卖出信号: {trade_sum['sell_signals']}")

        if report.get("position_checks", 0) > 0:
            console.print(f"  止损/止盈触发: {report['position_checks']}笔")

        trades = report.get("trades", [])
        if trades:
            console.print()
            table = Table(title="交易明细")
            table.add_column("代码", width=10)
            table.add_column("名称", width=10)
            table.add_column("方向", width=6)
            table.add_column("数量", width=6)
            table.add_column("价格", width=8)
            table.add_column("置信度", width=8)
            table.add_column("状态", width=10)

            for t in trades:
                action_style = f"[green]{t['action']}[/green]" if t['action'] == 'BUY' else f"[red]{t['action']}[/red]"
                status_style = {
                    "filled": "[green]已成交[/green]",
                    "rejected": "[red]已拒绝[/red]",
                    "dry_run": "[yellow]模拟[/yellow]",
                }.get(t["status"], t["status"])
                table.add_row(
                    t["symbol"], t["name"], action_style,
                    str(t["quantity"]), f"{t['price']:.2f}",
                    f"{t['confidence']:.1%}", status_style,
                )
            console.print(table)

        console.print(f"\n[cyan]交易报告: {output}/trade_report_{report['date']}.json[/cyan]")

        trader.stop()

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("自动交易失败")
        console.print(f"[red]自动交易失败: {e}[/red]")


@trade.command("estimate-impact")
@click.option("--symbol", "-s", required=True, help="股票代码")
@click.option("--quantity", "-q", type=int, required=True, help="订单数量")
@click.option("--price", "-p", type=float, default=None, help="到达价格（默认用最新价）")
@click.pass_context
def estimate_impact(ctx, symbol, quantity, price):
    """估算市场冲击成本"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        impact_model = MarketImpactModel()

        daily_volume = store.fetch_daily_volume(symbol, days=20)

        df = store.fetch_daily(symbol, source="akshare", use_cache=True)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        if price is None:
            price = float(df["close"].iloc[-1])

        returns = df["close"].pct_change().dropna()
        daily_volatility = float(returns.std())

        impact = impact_model.estimate_impact(
            symbol=symbol,
            order_quantity=quantity,
            order_side="BUY",
            arrival_price=price,
            daily_volume=daily_volume,
            daily_volatility=daily_volatility,
        )

        console.print(
            Panel.fit(
                f"[bold]股票:[/bold] {impact.symbol}\n"
                f"[bold]订单量:[/bold] {impact.order_quantity:,} 股\n"
                f"[bold]到达价格:[/bold] {impact.arrival_price:.4f}\n"
                f"[bold]日均成交量:[/bold] {impact.daily_volume:,.0f}\n"
                f"[bold]日波动率:[/bold] {impact.daily_volatility:.4f}\n"
                f"[bold]临时冲击:[/bold] {impact.temporary_impact_bps} bps\n"
                f"[bold]永久冲击:[/bold] {impact.permanent_impact_bps} bps\n"
                f"[bold]总冲击:[/bold] {impact.total_impact_bps} bps\n"
                f"[bold]预期成交价:[/bold] {impact.expected_slippage_price:.4f}",
                title="📊 市场冲击成本估算",
                border_style="cyan",
            )
        )
    except Exception as e:
        console.print(f"[red]估算失败: {e}[/red]")


@trade.command("execution-plan")
@click.option("--symbol", "-s", required=True, help="股票代码")
@click.option("--quantity", "-q", type=int, required=True, help="总订单数量")
@click.option("--strategy", "-st", default="vwap", help="执行策略 (twap/vwap/implementation_shortfall)")
@click.option("--minutes", "-m", default=30, help="执行时间（分钟）")
@click.option("--slices", "-n", default=10, help="子单数量")
@click.pass_context
def execution_plan(ctx, symbol, quantity, strategy, minutes, slices):
    """生成执行计划"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        impact_model = MarketImpactModel()
        scheduler = ExecutionScheduler(impact_model=impact_model)

        volume_profile_obj = VolumeProfile()
        profile = volume_profile_obj.get_profile(slices)

        schedule = scheduler.generate_schedule(
            symbol=symbol,
            total_quantity=quantity,
            strategy=strategy,
            total_minutes=minutes,
            num_slices=slices,
            volume_profile=profile,
        )

        console.print(
            Panel.fit(
                f"[bold]策略:[/bold] {schedule.strategy}\n"
                f"[bold]总订单量:[/bold] {schedule.total_quantity:,}\n"
                f"[bold]子单数:[/bold] {schedule.num_slices}\n"
                f"[bold]预期均价:[/bold] {schedule.expected_avg_price:.4f}\n"
                f"[bold]预期冲击:[/bold] {schedule.expected_impact_bps} bps",
                title="📋 执行计划",
                border_style="cyan",
            )
        )

        table = Table(title="子单明细")
        table.add_column("#", style="white", width=4)
        table.add_column("时间偏移(min)", style="cyan")
        table.add_column("数量", style="green")

        for slc in schedule.slices:
            table.add_row(
                str(slc.slice_index + 1),
                f"{slc.time_offset_minutes:.1f}",
                f"{slc.quantity:,}",
            )
        console.print(table)

    except Exception as e:
        console.print(f"[red]生成执行计划失败: {e}[/red]")


@trade.command("tca-report")
@click.option("--period", "-p", default="this_week", help="报告周期")
@click.pass_context
def tca_report(ctx, period):
    """输出TCA报告"""
    try:
        analyzer = TransactionCostAnalyzer()

        report = analyzer.generate_weekly_report()

        console.print(
            Panel.fit(
                f"[bold]周期:[/bold] {report.period_start} ~ {report.period_end}\n"
                f"[bold]订单数:[/bold] {len(report.records)}\n"
                f"[bold]平均执行成本:[/bold] {report.avg_execution_cost_bps:.2f} bps",
                title="📊 TCA 周度报告",
                border_style="cyan",
            )
        )

        percentiles = report.cost_percentiles()
        console.print(
            f"[bold]成本分布:[/bold] "
            f"P25={percentiles['P25']}bps P50={percentiles['P50']}bps "
            f"P75={percentiles['P75']}bps P95={percentiles['P95']}bps"
        )

        if report.by_symbol:
            table = Table(title="按股票统计")
            table.add_column("股票", style="cyan")
            table.add_column("订单数", style="white")
            table.add_column("平均成本(bps)", style="yellow")
            table.add_column("总股数", style="green")

            for sym, data in report.by_symbol.items():
                table.add_row(
                    sym,
                    str(data["count"]),
                    f"{data['avg_cost_bps']:.2f}",
                    f"{data['total_quantity']:,.0f}",
                )
            console.print(table)

    except Exception as e:
        console.print(f"[red]TCA报告生成失败: {e}[/red]")


@trade.command("tca-order")
@click.option("--order-id", "-o", required=True, help="订单ID")
@click.pass_context
def tca_order(ctx, order_id):
    """查看单笔订单TCA明细"""
    try:
        analyzer = TransactionCostAnalyzer()
        record = analyzer.get_order_tca(order_id)

        if record is None:
            console.print(f"[yellow]未找到订单: {order_id}[/yellow]")
            return

        console.print(
            Panel.fit(
                f"[bold]订单ID:[/bold] {record.order_id}\n"
                f"[bold]股票:[/bold] {record.symbol}\n"
                f"[bold]方向:[/bold] {record.side}\n"
                f"[bold]数量:[/bold] {record.quantity:,.0f}\n"
                f"[bold]到达价:[/bold] {record.arrival_price:.4f}\n"
                f"[bold]成交均价:[/bold] {record.execution_avg_price:.4f}\n"
                f"[bold]VWAP:[/bold] {record.vwap:.4f}\n"
                f"[bold]IS (bps):[/bold] {record.is_bps}\n"
                f"[bold]延迟成本 (bps):[/bold] {record.delay_bps}\n"
                f"[bold]冲击成本 (bps):[/bold] {record.impact_bps}",
                title=f"📋 TCA 明细 - {order_id}",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]TCA查询失败: {e}[/red]")


@trade.command("covariance")
@click.option("--symbols", "-s", required=True, help="股票代码（逗号分隔）")
@click.option("--method", "-m", default="ledoit_wolf", help="方法 (sample/exponential/ledoit_wolf)")
@click.pass_context
def calc_covariance(ctx, symbols, method):
    """计算协方差矩阵和相关性矩阵"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)
    symbols_list = [s.strip() for s in symbols.split(",")]

    try:
        returns_data = {}
        for sym in symbols_list:
            df = store.fetch_daily(sym, source="akshare", use_cache=True)
            if "close" in df.columns:
                returns_data[sym] = df["close"].pct_change().dropna()

        returns_df = pd.DataFrame(returns_data).dropna()
        if returns_df.empty:
            console.print("[red]未获取到有效数据[/red]")
            return

        import pandas as pd

        estimator = CovarianceEstimator()
        result = estimator.estimate(returns_df, method=method)

        console.print(
            Panel.fit(
                f"[bold]方法:[/bold] {result.method}\n"
                f"[bold]收缩强度:[/bold] {result.shrinkage_intensity:.4f}\n"
                f"[bold]正定性:[/bold] {'✓' if result.is_positive_definite else '✗'}",
                title="📊 协方差矩阵估计",
                border_style="cyan",
            )
        )

        table = Table(title="相关性矩阵")
        table.add_column("", style="white")
        for sym in symbols_list:
            table.add_column(sym, style="cyan")

        for sym_i in symbols_list:
            row = [sym_i]
            for sym_j in symbols_list:
                val = result.correlation_matrix.loc[sym_i, sym_j]
                color = "green" if val > 0.7 else "red" if val < -0.7 else "white"
                row.append(f"[{color}]{val:.3f}[/{color}]")
            table.add_row(*row)

        console.print(table)

    except Exception as e:
        console.print(f"[red]协方差计算失败: {e}[/red]")


@trade.command("optimize-portfolio")
@click.option("--symbols", "-s", required=True, help="股票代码（逗号分隔）")
@click.option("--method", "-m", default="markowitz", help="方法 (markowitz/risk_parity/hrp)")
@click.pass_context
def optimize_portfolio(ctx, symbols, method):
    """组合优化"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)
    symbols_list = [s.strip() for s in symbols.split(",")]

    try:
        returns_data = {}
        close_prices = {}
        for sym in symbols_list:
            df = store.fetch_daily(sym, source="akshare", use_cache=True)
            if "close" in df.columns:
                returns_data[sym] = df["close"].pct_change().dropna()
                close_prices[sym] = df["close"].iloc[-1]

        returns_df = pd.DataFrame(returns_data).dropna()
        if returns_df.empty:
            console.print("[red]未获取到有效数据[/red]")
            return

        import pandas as pd

        estimator = CovarianceEstimator()
        cov_result = estimator.estimate(returns_df)

        if method == "markowitz":
            expected_returns = {sym: float(returns_df[sym].mean() * 252) for sym in symbols_list}
            optimizer = PortfolioOptimizer()
            allocation = optimizer.optimize(expected_returns, cov_result.covariance_matrix)
        elif method == "risk_parity":
            optimizer = RiskParityOptimizer()
            allocation = optimizer.optimize(cov_result.covariance_matrix)
        elif method == "hrp":
            optimizer = HRPOptimizer()
            allocation = optimizer.optimize(cov_result.covariance_matrix)
        else:
            console.print(f"[red]未知方法: {method}[/red]")
            return

        console.print(
            Panel.fit(
                f"[bold]方法:[/bold] {allocation.method}\n"
                f"[bold]预期年化收益:[/bold] {allocation.expected_portfolio_return:.4%}\n"
                f"[bold]预期年化波动:[/bold] {allocation.expected_portfolio_volatility:.4%}\n"
                f"[bold]夏普比率:[/bold] {allocation.sharpe_ratio:.4f}\n"
                f"[bold]分散化比率:[/bold] {allocation.diversification_ratio:.2f}",
                title="📊 组合优化结果",
                border_style="cyan",
            )
        )

        table = Table(title="最优权重")
        table.add_column("股票", style="cyan")
        table.add_column("权重", style="green")
        table.add_column("配置", style="yellow")

        for sym, w in sorted(allocation.weights.items(), key=lambda x: -x[1]):
            bar_len = int(w * 40)
            bar = "█" * bar_len
            table.add_row(sym, f"{w:.4f}", f"[green]{bar}[/green]")

        console.print(table)

    except Exception as e:
        console.print(f"[red]组合优化失败: {e}[/red]")


@trade.command("factor-exposure")
@click.option("--symbols", "-s", required=True, help="股票代码（逗号分隔）")
@click.pass_context
def factor_exposure_cmd(ctx, symbols):
    """输出因子暴露"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)
    symbols_list = [s.strip() for s in symbols.split(",")]

    try:
        returns_data = {}
        for sym in symbols_list:
            df = store.fetch_daily(sym, source="akshare", use_cache=True)
            if "close" in df.columns:
                returns_data[sym] = df["close"].pct_change().dropna()

        returns_df = pd.DataFrame(returns_data).dropna()
        if returns_df.empty:
            console.print("[red]未获取到有效数据[/red]")
            return

        import pandas as pd

        model = FactorModel()
        model.fit(returns_df)

        equal_weights = {sym: 1.0 / len(symbols_list) for sym in symbols_list}
        exposure = model.get_factor_exposures(equal_weights, returns_df)

        console.print(
            Panel.fit(
                f"[bold]总年化收益:[/bold] {exposure.total_return:.4%}\n"
                f"[bold]特质收益 (Alpha):[/bold] {exposure.specific_return:.4%}\n"
                f"[bold]Alpha占比:[/bold] {exposure.alpha_pct:.1f}%",
                title="📊 因子暴露分析",
                border_style="cyan",
            )
        )

        table = Table(title="因子贡献")
        table.add_column("因子", style="cyan")
        table.add_column("暴露", style="white")
        table.add_column("因子收益(年化)", style="yellow")
        table.add_column("贡献收益(年化)", style="green")

        for name, data in exposure.factor_exposures.items():
            table.add_row(
                name,
                f"{data['exposure']:.4f}",
                f"{data['factor_return_annualized']:.4%}",
                f"{data['contribution_annualized']:.4%}",
            )
        console.print(table)

    except Exception as e:
        console.print(f"[red]因子暴露分析失败: {e}[/red]")


@trade.command("find-pairs")
@click.option("--pool", "-p", default="hs300", help="股票池")
@click.option("--symbols", "-s", default=None, help="自定义股票代码（逗号分隔）")
@click.pass_context
def find_pairs(ctx, pool, symbols):
    """发现协整配对"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        if symbols:
            symbols_list = [s.strip() for s in symbols.split(",")]
        else:
            symbols_list = ["000001", "000858", "600519", "600036", "601318",
                           "000333", "600276", "300750", "000651", "002415"]

        console.print(f"[cyan]正在扫描 {len(symbols_list)} 只股票的协整关系...[/cyan]")

        price_data = {}
        for sym in symbols_list:
            df = store.fetch_daily(sym, source="akshare", use_cache=True)
            if not df.empty:
                price_data[sym] = df

        strategy = PairsTradingStrategy()
        pairs = strategy.discover_pairs(price_data, symbols_list)

        if not pairs:
            console.print("[yellow]未发现协整配对[/yellow]")
            return

        console.print(f"[green]发现 {len(pairs)} 个协整配对[/green]")

        table = Table(title="协整配对")
        table.add_column("股票Y", style="cyan")
        table.add_column("股票X", style="cyan")
        table.add_column("对冲比率", style="white")
        table.add_column("ADF t-stat", style="yellow")
        table.add_column("p-value", style="red")
        table.add_column("相关性", style="green")

        for pair in pairs:
            table.add_row(
                pair.symbol_y, pair.symbol_x,
                f"{pair.hedge_ratio:.4f}",
                f"{pair.adf_t_stat:.2f}",
                f"{pair.p_value:.4f}",
                f"{pair.correlation:.4f}",
            )
        console.print(table)

    except Exception as e:
        console.print(f"[red]配对发现失败: {e}[/red]")


@trade.command("hmm-state")
@click.option("--symbol", "-s", default="000300", help="指数代码")
@click.pass_context
def hmm_state(ctx, symbol):
    """HMM市场状态识别"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        df = store.fetch_daily(symbol, source="akshare", use_cache=True)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        detector = HMMRegimeDetector()
        features = detector.prepare_features(df)

        trained = detector.load_model() or detector.fit(features)

        if not trained:
            console.print("[red]HMM训练失败[/red]")
            return

        result = detector.predict_state(features)

        state_colors = {0: "green", 1: "red", 2: "yellow"}

        console.print(
            Panel.fit(
                f"[bold]当前状态:[/bold] [{state_colors.get(result.current_regime, 'white')}]{result.dominant_regime_label}[/{state_colors.get(result.current_regime, 'white')}]\n"
                + "\n".join(
                    f"[bold]状态{i}:[/bold] P={result.state_probabilities[i]:.3f} "
                    f"[{state_colors.get(i, 'white')}]{result.regime_characteristics.get(i, {}).get('label', f'State_{i}')}[/{state_colors.get(i, 'white')}]"
                    for i in range(min(3, len(result.state_probabilities)))
                ),
                title="🤖 HMM 市场状态",
                border_style="cyan",
            )
        )

        if result.regime_characteristics:
            table = Table(title="状态特征")
            table.add_column("状态", style="cyan")
            table.add_column("标签", style="white")
            table.add_column("平均20日收益", style="yellow")
            table.add_column("平均20日波动", style="red")
            table.add_column("频率", style="green")

            for state, chars in result.regime_characteristics.items():
                table.add_row(
                    f"State_{state}",
                    chars["label"],
                    f"{chars['avg_20d_return']:.4%}",
                    f"{chars['avg_20d_volatility']:.4%}",
                    f"{chars['frequency']:.2%}",
                )
            console.print(table)

    except Exception as e:
        console.print(f"[red]HMM分析失败: {e}[/red]")


@trade.command("kalman-hedge")
@click.option("--pair", "-p", required=True, help="配对代码 (如000001-000858)")
@click.pass_context
def kalman_hedge(ctx, pair):
    """卡尔曼滤波动态对冲比率"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        parts = pair.split("-")
        if len(parts) != 2:
            console.print("[red]配对格式错误，应为 SYMBOL1-SYMBOL2[/red]")
            return

        sym_y, sym_x = parts

        df_y = store.fetch_daily(sym_y, source="akshare", use_cache=True)
        df_x = store.fetch_daily(sym_x, source="akshare", use_cache=True)

        if df_y.empty or df_x.empty:
            console.print("[red]未获取到数据[/red]")
            return

        y_close = df_y["close"].values
        x_close = df_x["close"].values
        min_len = min(len(y_close), len(x_close))
        y_close = y_close[-min_len:]
        x_close = x_close[-min_len:]

        kf = KalmanHedgeRatio()
        estimates = []
        for i in range(len(y_close)):
            est = kf.update(float(y_close[i]), float(x_close[i]))
            estimates.append(est)

        ols_hedge = float(np.polyfit(x_close, y_close, 1)[0])

        console.print(
            Panel.fit(
                f"[bold]配对:[/bold] {sym_y}-{sym_x}\n"
                f"[bold]OLS对冲比率:[/bold] {ols_hedge:.6f}\n"
                f"[bold]卡尔曼最终β:[/bold] {kf.beta:.6f}\n"
                f"[bold]β标准差:[/bold] {kf.beta_std:.6f}\n"
                f"[bold]更新次数:[/bold] {kf.n_updates}",
                title="📈 卡尔曼滤波对冲比率",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]卡尔曼滤波失败: {e}[/red]")


@trade.command("vol-forecast")
@click.option("--symbol", "-s", required=True, help="股票代码")
@click.option("--method", "-m", default="ewma", help="方法 (ewma/garch)")
@click.pass_context
def vol_forecast(ctx, symbol, method):
    """波动率预测"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        df = store.fetch_daily(symbol, source="akshare", use_cache=True)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        returns = df["close"].pct_change().dropna()

        forecaster = VolatilityForecaster()
        forecast = forecaster.forecast(returns, method=method, horizon=5)

        console.print(
            Panel.fit(
                f"[bold]方法:[/bold] {forecast['method']}\n"
                f"[bold]当前日波动率:[/bold] {forecast['current_daily_vol']:.4%}\n"
                + "\n".join(
                    f"[bold]预测 Day {i}:[/bold] {forecast[f'forecast_vol_{i}d']:.4%}"
                    for i in range(1, 6) if f"forecast_vol_{i}d" in forecast
                ),
                title=f"📈 {symbol} 波动率预测",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]波动率预测失败: {e}[/red]")


@trade.command("tick-analysis")
@click.option("--symbol", "-s", required=True, help="股票代码")
@click.pass_context
def tick_analysis(ctx, symbol):
    """tick数据分析"""
    try:
        import akshare as ak
        import pandas as pd

        console.print(f"[cyan]正在获取 {symbol} tick数据...[/cyan]")

        try:
            tick_df = ak.stock_zh_a_tick_tx(symbol=symbol)
        except Exception:
            try:
                tick_df = ak.stock_zh_a_tick_js(code=symbol)
            except Exception:
                console.print("[red]无法获取tick数据[/red]")
                return

        if tick_df.empty:
            console.print("[red]未获取到tick数据[/red]")
            return

        extractor = OrderBookSignalExtractor()
        signal = extractor.extract(tick_df)

        score_color = "green" if signal["composite_score"] > 0.2 else "red" if signal["composite_score"] < -0.2 else "yellow"

        console.print(
            Panel.fit(
                f"[bold]成交量不平衡:[/bold] {signal['volume_imbalance']:.4f}\n"
                f"[bold]单笔大小不平衡:[/bold] {signal['trade_size_imbalance']:.4f}\n"
                f"[bold]Tick方向:[/bold] {signal['tick_direction']:.4f}\n"
                f"[bold]综合评分:[/bold] [{score_color}]{signal['composite_score']:.4f}[/{score_color}]\n"
                f"[bold]买方成交量:[/bold] {signal['buy_volume']:,.0f}\n"
                f"[bold]卖方成交量:[/bold] {signal['sell_volume']:,.0f}",
                title=f"📊 {symbol} Tick 分析",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]tick分析失败: {e}[/red]")


@trade.command("test-significance")
@click.option("--strategy", "-s", required=True, help="策略名称")
@click.option("--symbol", "-y", default="000001", help="股票代码")
@click.option("--n-trials", "-n", type=int, default=50, help="尝试的参数组合数")
@click.pass_context
def test_significance(ctx, strategy, symbol, n_trials):
    """测试策略统计显著性"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        if strategy not in STRATEGY_REGISTRY:
            console.print(f"[red]未知策略: {strategy}[/red]")
            return

        df = store.fetch_daily(symbol, source="akshare", use_cache=True)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        strat = create_strategy(strategy)
        engine = BacktestEngine(strategy=strat, initial_capital=100000, risk_config=config.risk)
        result = engine.run(df, symbol=symbol)

        import pandas as pd
        returns = pd.Series(result.equity_curve).pct_change().dropna()

        tester = StrategySignificanceTester(n_simulations=2000)
        sig_report = tester.test(strategy_returns=returns.values, n_trials=n_trials)

        level_colors = {
            "HIGHLY SIGNIFICANT": "bold green",
            "SIGNIFICANT": "green",
            "WEAK": "yellow",
            "NOT SIGNIFICANT": "red",
        }

        console.print(
            Panel.fit(
                f"[bold]原始Sharpe:[/bold] {sig_report.sharpe_ratio:.4f}\n"
                f"[bold]Deflated Sharpe:[/bold] {sig_report.deflated_sharpe:.4f}\n"
                f"[bold]Haircut Sharpe:[/bold] {sig_report.haircut_sharpe:.4f}\n"
                f"[bold]月度Alpha t-stat:[/bold] {sig_report.monthly_alpha_t_stat:.4f}\n"
                f"[bold]显著性:[/bold] [{level_colors.get(sig_report.significance_level, 'white')}]{sig_report.significance_level}[/{level_colors.get(sig_report.significance_level, 'white')}]\n"
                f"[bold]尝试次数:[/bold] {sig_report.n_trials}\n"
                f"[bold]Monte Carlo模拟:[/bold] {sig_report.n_simulations}",
                title="🔬 策略显著性检验",
                border_style="cyan",
            )
        )

    except Exception as e:
        console.print(f"[red]显著性检验失败: {e}[/red]")


@trade.command("backtest-mc")
@click.option("--symbol", "-s", default="000001", help="股票代码")
@click.option("--strategy", "-st", default="trend_following", help="策略名称")
@click.option("--n-paths", "-n", type=int, default=500, help="Monte Carlo路径数")
@click.pass_context
def backtest_mc(ctx, symbol, strategy, n_paths):
    """Monte Carlo概率回测"""
    config = ctx.obj["config"]
    store = DataStore(cache_dir=config.data.cache_dir, db_url=config.data.database_url)

    try:
        if strategy not in STRATEGY_REGISTRY:
            console.print(f"[red]未知策略: {strategy}[/red]")
            return

        df = store.fetch_daily(symbol, source="akshare", use_cache=True)
        if df.empty:
            console.print("[red]未获取到数据[/red]")
            return

        strat = create_strategy(strategy)
        engine = BacktestEngine(strategy=strat, initial_capital=100000, risk_config=config.risk)

        console.print(f"[cyan]正在运行 {n_paths} 路径 Monte Carlo 回测...[/cyan]")

        prob_engine = ProbabilisticBacktestEngine(engine=engine, n_paths=n_paths)
        mc_result = prob_engine.run_probabilistic_montecarlo(data=df, symbol=symbol)

        console.print(
            Panel.fit(
                f"[bold]路径数:[/bold] {mc_result.n_paths}\n"
                f"[bold]最终权益中位数:[/bold] {mc_result.final_equity_distribution['P50']:,.2f}\n"
                f"[bold]亏损概率:[/bold] {mc_result.prob_of_loss:.2%}\n"
                f"[bold]预期夏普:[/bold] {mc_result.expected_sharpe:.4f}",
                title="🎲 Monte Carlo 回测结果",
                border_style="cyan",
            )
        )

        table = Table(title="最终权益分布")
        table.add_column("分位数", style="cyan")
        table.add_column("最终权益", style="green")

        for key in ["P10", "P25", "P50", "P75", "P90"]:
            table.add_row(key, f"{mc_result.final_equity_distribution[key]:,.2f}")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Monte Carlo回测失败: {e}[/red]")


@cli.command("init")
def init_project():
    """初始化项目目录和配置"""
    dirs = ["./data/cache", "./logs", "./config"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] 创建目录 {d}")

    config_path = Path("./config/default.yaml")
    if not config_path.exists():
        AppConfig.save_default(config_path)
        console.print(f"[green]✓[/green] 创建默认配置 {config_path}")
    else:
        console.print(f"[yellow]○[/yellow] 配置文件已存在 {config_path}")

    console.print("\n[bold green]项目初始化完成！[/bold green]")
    console.print("[cyan]使用 'trading --help' 查看可用命令[/cyan]")


if __name__ == "__main__":
    cli()
