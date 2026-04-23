from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading_system.analysis.market import MarketAnalyzer
from trading_system.backtest.engine import BacktestEngine
from trading_system.backtest.report import display_backtest_result
from trading_system.core.config import AppConfig
from trading_system.core.logging_config import setup_logging
from trading_system.data.store import DataStore
from trading_system.data.watchlist import WatchlistManager
from trading_system.execution.engine import TradingEngine
from trading_system.research.engine import ResearchEngine
from trading_system.research.sources import ResearchDataAggregator
from trading_system.sentiment.analyzer import MarketSentimentAnalyzer, SentimentLevel
from trading_system.sentiment.hotspot import HotSpotDetector
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
@click.option(
    "--mode", "-m", type=click.Choice(["paper", "live"]), default="paper", help="交易模式"
)
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
@click.pass_context
def recommend_stocks(ctx, top, output):
    """生成每日推荐报告"""
    from trading_system.advisor.daily_report import DailyReportGenerator
    from trading_system.advisor.entry_exit import EntryExitAdvisor
    from trading_system.scorer.engine import StockScorer

    console.print("[cyan]正在生成每日推荐报告...[/cyan]")
    try:
        scorer = StockScorer()
        advisor = EntryExitAdvisor(scorer)
        generator = DailyReportGenerator(scorer=scorer, advisor=advisor, output_dir=output)

        demo_stocks = [
            ("600519", {"name": "贵州茅台", "rsi": 45, "ma_bullish": True, "volume_ratio": 1.5,
                        "volatility": 0.15, "pe_ttm": 30, "pb": 10, "roe": 25,
                        "revenue_growth": 15, "north_net_inflow": 100, "main_net_inflow": 50,
                        "on_dragon_tiger": False, "news_sentiment": 0.2, "sector_heat": 70,
                        "market_mood": 60}),
            ("000001", {"name": "平安银行", "rsi": 40, "ma_bullish": False, "volume_ratio": 0.8,
                        "volatility": 0.2, "pe_ttm": 5.5, "pb": 0.6, "roe": 11,
                        "revenue_growth": 8, "north_net_inflow": 50, "main_net_inflow": 20,
                        "on_dragon_tiger": False, "news_sentiment": 0.1, "sector_heat": 40,
                        "market_mood": 50}),
            ("300750", {"name": "宁德时代", "rsi": 55, "ma_bullish": True, "volume_ratio": 2.0,
                        "volatility": 0.25, "pe_ttm": 50, "pb": 8, "roe": 15,
                        "revenue_growth": 40, "north_net_inflow": 200, "main_net_inflow": 80,
                        "on_dragon_tiger": True, "news_sentiment": 0.3, "sector_heat": 85,
                        "market_mood": 70}),
        ]

        scores = scorer.rank_stocks(demo_stocks)
        recommendations = []
        for s in scores[:top]:
            rec = advisor.recommend_entry(s.symbol, 100.0, s.details)
            recommendations.append(rec)

        market_summary = {"北向资金": "净流入 150亿", "市场情绪": "偏多", "涨跌比": "2800:1800"}
        generator.generate_report(scores, recommendations, market_summary)
        console.print("[green]推荐报告已生成！[/green]")
        console.print(f"[cyan]报告路径: {output}[/cyan]")
    except Exception as e:
        console.print(f"[red]推荐报告生成失败: {e}[/red]")


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
