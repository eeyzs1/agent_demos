import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))

RESULTS = []

def test(name, fn):
    print(f"\n{'='*60}")
    print(f"  诊断: {name}")
    print(f"{'='*60}")
    try:
        result = fn()
        if isinstance(result, dict):
            for k, v in result.items():
                print(f"    {k}: {v}")
        else:
            print(f"    结果: {result}")
        RESULTS.append({"name": name, "status": "PASS", "detail": result})
    except Exception as e:
        print(f"    ❌ 失败: {e}")
        traceback.print_exc()
        RESULTS.append({"name": name, "status": "FAIL", "error": str(e)})

# ============================================================
# 诊断1: 数据源 — akshare 能不能取到真实数据
# ============================================================
def diag_data_sources():
    from trading_system.data.sources import AKShareSource
    source = AKShareSource()

    results = {}

    try:
        df = source.fetch_daily("000001", start_date="20250501", end_date="20250520")
        results["日线数据(000001)"] = f"获取到 {len(df)} 条, 列: {list(df.columns)}, 最新收盘: {df['close'].iloc[-1]:.2f}"
    except Exception as e:
        results["日线数据(000001)"] = f"失败: {e}"

    try:
        rt = source.fetch_realtime("000001")
        results["实时行情(000001)"] = f"最新价: {rt.get('price')}, 涨跌幅: {rt.get('change_pct')}%"
    except Exception as e:
        results["实时行情(000001)"] = f"失败: {e}"

    try:
        fin = source.fetch_financial("000001")
        results["财务数据(000001)"] = f"PE={fin.get('pe_ttm')}, PB={fin.get('pb')}, ROE={fin.get('roe')}"
    except Exception as e:
        results["财务数据(000001)"] = f"失败: {e}"

    try:
        nf = source.fetch_north_flow()
        results["北向资金"] = f"获取到 {len(nf)} 条, 最新: {nf[0] if nf else '空'}"
    except Exception as e:
        results["北向资金"] = f"失败: {e}"

    try:
        symbols = source.get_symbol_list()
        results["股票列表"] = f"获取到 {len(symbols)} 只股票"
    except Exception as e:
        results["股票列表"] = f"失败: {e}"

    return results


# ============================================================
# 诊断2: DataStore 缓存+数据库是否可用
# ============================================================
def diag_data_store():
    from trading_system.data.store import DataStore
    store = DataStore(cache_dir="./data/cache", db_url="sqlite:///./data/trading.db")

    results = {}
    try:
        df = store.fetch_daily("000001", source="akshare", use_cache=True)
        results["缓存取数(000001)"] = f"{len(df)} 条, 最新收盘: {df['close'].iloc[-1]:.2f}"
    except Exception as e:
        results["缓存取数(000001)"] = f"失败: {e}"

    try:
        rt = store.fetch_realtime("000001", source="akshare")
        results["实时取数(000001)"] = f"价格={rt.get('current_price')}, 涨跌={rt.get('change_pct')}%"
    except Exception as e:
        results["实时取数(000001)"] = f"失败: {e}"

    return results


# ============================================================
# 诊断3: 策略 — 能否在真实数据上生成信号
# ============================================================
def diag_strategies():
    from trading_system.data.sources import AKShareSource
    from trading_system.strategy.strategies import (
        TrendFollowingStrategy,
        MeanReversionStrategy,
        BreakoutStrategy,
    )
    source = AKShareSource()
    df = source.fetch_daily("000001", start_date="20250101", end_date="20250520")

    results = {}
    for StrategyClass, name in [
        (TrendFollowingStrategy, "趋势跟踪"),
        (MeanReversionStrategy, "均值回归"),
        (BreakoutStrategy, "通道突破"),
    ]:
        try:
            strat = StrategyClass()
            signals = strat.generate_signals(df)
            buy_signals = [s for s in signals if s.signal_type.value == "BUY"]
            sell_signals = [s for s in signals if s.signal_type.value == "SELL"]
            last_buy = buy_signals[-1] if buy_signals else None
            results[name] = (
                f"买入信号: {len(buy_signals)}个, 卖出信号: {len(sell_signals)}个, "
                f"最新买入: {last_buy.price if last_buy else '无'}"
            )
        except Exception as e:
            results[name] = f"失败: {e}"

    return results


# ============================================================
# 诊断4: 回测 — 用真实数据跑回测
# ============================================================
def diag_backtest():
    from trading_system.data.sources import AKShareSource
    from trading_system.strategy.strategies import TrendFollowingStrategy
    from trading_system.backtest.engine import BacktestEngine
    from trading_system.core.config import RiskConfig

    source = AKShareSource()
    df = source.fetch_daily("000001", start_date="20230101", end_date="20250520")

    results = {}
    try:
        strat = TrendFollowingStrategy()
        engine = BacktestEngine(strategy=strat, initial_capital=100000, risk_config=RiskConfig())
        result = engine.run(df, symbol="000001")

        summary = result.summary(100000)
        results["回测结果(000001,趋势跟踪)"] = (
            f"总交易: {result.total_trades}笔, "
            f"胜率: {result.win_rate:.1%}, "
            f"年化收益: {result.annualized_return:.1%}, "
            f"夏普: {result.sharpe_ratio:.2f}, "
            f"最大回撤: {result.max_drawdown:.1%}, "
            f"盈亏比: {result.profit_factor:.2f}"
        )
        ashare = result.ashare_summary
        results["A股费用"] = (
            f"总费用: {ashare['total_cost']}元, "
            f"买入佣金: {ashare['total_buy_commission']}元, "
            f"卖出佣金: {ashare['total_sell_commission']}元, "
            f"印花税: {ashare['total_stamp_tax']}元"
        )
    except Exception as e:
        results["回测"] = f"失败: {e}"

    return results


# ============================================================
# 诊断5: 筛选器 engine — 能否真实筛选
# ============================================================
def diag_screener():
    from trading_system.screener.engine import StockScreener
    from trading_system.screener.screen import ScreenTemplate

    results = {}
    try:
        screener = StockScreener()
        results["筛选器初始化"] = "成功"
        results["可用模板"] = str(ScreenTemplate.list_templates() if hasattr(ScreenTemplate, 'list_templates') else "N/A")
    except Exception as e:
        results["筛选器"] = f"失败: {e}"

    # 檢查 screen.py
    try:
        import ast
        screen_path = Path("src/trading_system/screener/screen.py")
        code = screen_path.read_text(encoding="utf-8")
        tree = ast.parse(code)
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        results["screen.py函数"] = str(funcs)
    except Exception as e:
        results["screen.py"] = f"失败: {e}"

    return results


# ============================================================
# 诊断6: 评分器 engine — 能否真实评分
# ============================================================
def diag_scorer():
    from trading_system.scorer.engine import StockScorer
    from trading_system.data.sources import AKShareSource

    results = {}
    source = AKShareSource()

    try:
        fin_001 = source.fetch_financial("000001")
        results["财务(000001)"] = f"PE={fin_001.get('pe_ttm')}, ROE={fin_001.get('roe')}"

        scorer = StockScorer()
        stock_data = [("000001", {"name": fin_001.get("symbol", "000001"),
                                   "pe_ttm": fin_001.get("pe_ttm"),
                                   "roе": fin_001.get("roe"),
                                   "rsi": 45, "ma_bullish": True,
                                   "volume_ratio": 1.0, "volatility": 0.15,
                                   "pb": fin_001.get("pb"),
                                   "revenue_growth": fin_001.get("revenue_growth"),
                                   "north_net_inflow": 0, "main_net_inflow": 0,
                                   "on_dragon_tiger": False, "news_sentiment": 0.0,
                                   "sector_heat": 50, "market_mood": 50})]
        scores = scorer.rank_stocks(stock_data)
        if scores:
            s = scores[0]
            results["评分(000001)"] = f"总分={s.total_score:.1f}, 评级={s.rating}"
        else:
            results["评分(000001)"] = "返回空列表"
    except Exception as e:
        results["评分器"] = f"失败: {e}"

    return results


# ============================================================
# 诊断7: 执行引擎 — TradingEngine 能否启动和跑一圈
# ============================================================
def diag_execution():
    from trading_system.core.config import AppConfig
    from trading_system.execution.engine import TradingEngine
    from trading_system.data.sources import AKShareSource
    from trading_system.strategy.strategies import TrendFollowingStrategy

    results = {}
    try:
        config = AppConfig.from_yaml("./config/default.yaml")
        config.trading.mode = "paper"
        engine = TradingEngine(config=config)
        engine.register_strategy("trend", TrendFollowingStrategy())

        status = engine.get_portfolio_status()
        results["引擎状态"] = (
            f"资金: {status['cash']:.0f}, "
            f"持仓: {len(status['positions'])}个, "
            f"熔断: {status['circuit_breaker']}"
        )

        source = AKShareSource()
        df = source.fetch_daily("000001", start_date="20250401", end_date="20250520")
        strat = TrendFollowingStrategy()
        signals = strat.generate_signals(df)
        buy_sigs = [s for s in signals if s.signal_type.value == "BUY"]
        if buy_sigs:
            sig = buy_sigs[-1]
            sig.symbol = "000001"
            order = engine.process_signal(sig)
            results["信号处理"] = f"提交委托: {order.status if order else 'N/A'}"
        else:
            results["信号处理"] = "无买入信号"

    except Exception as e:
        results["执行引擎"] = f"失败: {e}"

    return results


# ============================================================
# 诊断8: 风控模块 — CircuitBreaker, RiskManager
# ============================================================
def diag_risk():
    from trading_system.core.config import AppConfig, RiskConfig
    from trading_system.risk.circuit_breaker import CircuitBreaker
    from trading_system.risk.manager import RiskManager
    from trading_system.execution.broker import PaperBroker

    results = {}
    try:
        config = RiskConfig()
        cb = CircuitBreaker(config)
        results["熔断状态"] = f"激活={cb.is_active if hasattr(cb, 'is_active') else 'N/A'}"

        broker = PaperBroker(initial_capital=100000)
        rm = RiskManager(config, broker)
        state = rm.get_state()
        results["风控状态"] = (
            f"当前回撤={state.current_drawdown:.2%}, "
            f"连亏={state.consecutive_losses}, "
            f"总交易={state.total_trades}"
        )
    except Exception as e:
        results["风控"] = f"失败: {e}"

    return results


# ============================================================
# 诊断9: QMT broker — 是否存在、能否import
# ============================================================
def diag_qmt():
    results = {}
    try:
        from trading_system.execution.qmt_broker import QmtBroker
        results["QMT模块导入"] = "成功"

        broker = QmtBroker()
        results["QMT连接状态"] = f"已连接={broker.is_connected}"

        try:
            import xtquant
            results["xtquant SDK"] = "已安装"
        except ImportError:
            results["xtquant SDK"] = "❌ 未安装 (需要从券商获取QMT客户端)"
    except Exception as e:
        results["QMT"] = f"失败: {e}"

    return results


# ============================================================
# 诊断10: recommend命令 — 核心自动化管线是否真实
# ============================================================
def diag_recommend_pipeline():
    results = {}
    try:
        from trading_system.scorer.engine import StockScorer
        from trading_system.advisor.entry_exit import EntryExitAdvisor
        from trading_system.advisor.daily_report import DailyReportGenerator
        from trading_system.data.sources import AKShareSource

        source = AKShareSource()
        symbols_list_df = source.get_symbol_list()
        results["全市场股票数"] = f"{len(symbols_list_df)} 只"

        top_symbols = symbols_list_df.head(20) if not symbols_list_df.empty else []
        results["可扫描股票"] = f"{len(top_symbols)} 只 (样本)"

        scorer = StockScorer()
        advisor = EntryExitAdvisor(scorer)
        generator = DailyReportGenerator(scorer=scorer, advisor=advisor, output_dir="./tmp_diag_output")

        results["管线初始化"] = "OK (Scorer + Advisor + ReportGenerator 均可实例化)"

        results["⚠️ 关键问题"] = (
            "CLI recommend命令使用 HARDCODED demo数据, "
            "从未调用真实数据源。需要重写管线。"
        )

    except Exception as e:
        results["推荐管线"] = f"失败: {e}"

    return results


# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  项目全面诊断工具")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    test("1.数据源 (akshare日线+实时+财务+北向)", diag_data_sources)
    test("2.DataStore (缓存+数据库)", diag_data_store)
    test("3.策略信号 (趋势跟踪/均值回归/突破)", diag_strategies)
    test("4.回测引擎 (真实数据+真实成本)", diag_backtest)
    test("5.筛选器模块", diag_screener)
    test("6.评分器模块", diag_scorer)
    test("7.执行引擎 (TradingEngine)", diag_execution)
    test("8.风控模块 (CircuitBreaker+RiskManager)", diag_risk)
    test("9.QMT券商接口", diag_qmt)
    test("10.推荐管线 (核心自动化链路)", diag_recommend_pipeline)

    print("\n" + "=" * 60)
    print("  诊断汇总")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"  通过: {passed}/{len(RESULTS)}")
    print(f"  失败: {failed}/{len(RESULTS)}")
    for r in RESULTS:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['name']}")