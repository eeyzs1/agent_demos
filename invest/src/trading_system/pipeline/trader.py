import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from trading_system.core.config import AppConfig
from trading_system.execution.engine import TradingEngine
from trading_system.pipeline.fusion import DecisionFusionEngine, FusionDecision
from trading_system.pipeline.scan_recommend import ScanRecommendPipeline
from trading_system.risk.manager import RiskManager
from trading_system.scorer.engine import StockScorer
from trading_system.strategy.base import MarketState, Signal, SignalType

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    symbol: str
    name: str
    action: str
    quantity: int
    price: float
    confidence: float
    strategy: str
    status: str
    reason: str = ""
    order_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DailyTrader:
    def __init__(
        self,
        config: Optional[AppConfig] = None,
        output_dir: str = "./output",
    ):
        self._config = config or self._load_default_config()
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._engine = TradingEngine(self._config)
        self._engine.start()

        self._trade_log: list[TradeResult] = []

        mode = self._config.trading.mode
        logger.info("DailyTrader initialized (mode=%s, capital=%.0f)", mode, self._config.trading.initial_capital)

    @staticmethod
    def _load_default_config() -> AppConfig:
        config_dir = Path(__file__).parent.parent.parent.parent / "config"
        config_path = config_dir / "default.yaml"
        if config_path.exists():
            return AppConfig.from_yaml(config_path)
        return AppConfig()

    @property
    def risk_manager(self) -> RiskManager:
        return self._engine.risk_manager

    @property
    def portfolio(self) -> dict:
        return self._engine.get_portfolio_status()

    @property
    def trade_log(self) -> list[TradeResult]:
        return list(self._trade_log)

    def run(
        self,
        candidate_limit: int = 100,
        top_n: int = 20,
        dry_run: bool = False,
    ) -> dict:
        start_time = datetime.now()
        self._trade_log = []

        logger.info("=" * 50)
        logger.info("每日自动化交易启动 (dry_run=%s)", dry_run)
        logger.info("=" * 50)

        logger.info("[1/5] 全市场扫描 + 多因子评分")
        pipeline = ScanRecommendPipeline()
        stock_data_list, market_summary = pipeline.run(candidate_limit=candidate_limit)

        if not stock_data_list:
            logger.error("未获取到有效股票数据")
            return {"status": "failed", "error": "no_stock_data"}

        scorer = StockScorer()
        scores = scorer.rank_stocks(stock_data_list)
        logger.info("扫描 %d 只, 评分 %d 只", len(stock_data_list), len(scores))

        price_map = {code: d.get("price", 0) for code, d in stock_data_list}

        logger.info("[2/5] 持仓检查 (止损/止盈/T+1)")
        position_results = self._check_positions(price_map, dry_run)

        logger.info("[3/5] 策略融合决策")
        fusion_engine = DecisionFusionEngine()
        fusion_decisions = fusion_engine.fuse(scores, stock_data_list, top_n=min(top_n, len(scores)))

        buy_list = [d for d in fusion_decisions if d.fusion_action == "BUY"]
        sell_list = [d for d in fusion_decisions if d.fusion_action == "SELL"]
        logger.info("融合决策: BUY=%d SELL=%d HOLD=%d",
                    len(buy_list), len(sell_list),
                    len(fusion_decisions) - len(buy_list) - len(sell_list))

        logger.info("[4/5] 执行交易")
        trade_results = []

        for d in sell_list:
            tr = self._execute_decision(d, dry_run)
            trade_results.append(tr)

        remaining_capital = self._get_available_capital()
        for d in buy_list:
            if remaining_capital <= 0:
                logger.info("资金已用完，跳过剩余买入")
                break
            tr = self._execute_decision(d, dry_run)
            trade_results.append(tr)
            remaining_capital = self._get_available_capital()

        logger.info("[5/5] 生成执行报告")
        report = self._build_execution_report(
            position_results, trade_results, market_summary, start_time, dry_run
        )

        self._save_report(report)

        logger.info("每日交易完成: BUY=%d SELL=%d 持仓检查=%d",
                    sum(1 for t in trade_results if t.action == "BUY"),
                    sum(1 for t in trade_results if t.action == "SELL"),
                    len(position_results))

        return report

    def stop(self):
        self._engine.stop()
        logger.info("DailyTrader stopped")

    def _check_positions(self, price_map: dict[str, float], dry_run: bool) -> list[dict]:
        positions = self.risk_manager.positions
        if not positions:
            logger.info("当前无持仓")
            return []

        logger.info("当前持仓: %d 只", len(positions))
        for sym, pos in positions.items():
            cur_price = price_map.get(sym, pos.entry_price)
            pnl = pos.unrealized_pnl(cur_price)
            pnl_pct = (cur_price - pos.entry_price) / pos.entry_price * 100
            logger.info("  %s: 成本%.2f 现价%.2f 浮盈%.2f (%.1f%%) 持有%d天 %s",
                       sym, pos.entry_price, cur_price, pnl, pnl_pct,
                       pos.holding_days, "T+1锁定" if pos.is_t1_locked else "可卖")

        if dry_run:
            logger.info("[DRY RUN] 跳过持仓止损止盈检查")
            return []

        closed = self._engine.check_stop_loss_take_profit(price_map)
        if closed:
            logger.info("止损/止盈触发: %d 笔", len(closed))
            for t in closed:
                logger.info("  %s: %s 盈亏=%.2f 原因=%s",
                           t["symbol"], t["side"], t.get("pnl", 0), t.get("reason", ""))
        return closed

    def _execute_decision(self, decision: FusionDecision, dry_run: bool) -> TradeResult:
        signal_type = SignalType.BUY if decision.fusion_action == "BUY" else SignalType.SELL

        signal = Signal(
            symbol=decision.symbol,
            signal_type=signal_type,
            price=decision.price,
            timestamp=datetime.now(),
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            confidence=decision.fusion_confidence,
            strategy_name=self._strategy_label(decision),
            market_state=MarketState.UNKNOWN,
            metadata={
                "fusion_action": decision.fusion_action,
                "consensus": decision.strategy_consensus,
                "scorer_score": decision.scorer_score,
                "scorer_rating": decision.scorer_rating,
            },
        )

        if dry_run:
            logger.info("[DRY RUN] %s %s %s @ %.2f (置信度 %.1f%%)",
                       signal_type.value, decision.symbol, decision.name,
                       decision.price, decision.fusion_confidence * 100)
            return TradeResult(
                symbol=decision.symbol,
                name=decision.name,
                action=decision.fusion_action,
                quantity=0,
                price=decision.price,
                confidence=decision.fusion_confidence,
                strategy=signal.strategy_name,
                status="dry_run",
                reason="模拟运行，未实际下单",
            )

        filled = self._engine.process_signal(signal)

        if filled and filled.is_filled:
            qty = filled.filled_quantity or filled.quantity
            result = TradeResult(
                symbol=decision.symbol,
                name=decision.name,
                action=decision.fusion_action,
                quantity=qty,
                price=filled.filled_price or decision.price,
                confidence=decision.fusion_confidence,
                strategy=signal.strategy_name,
                status="filled",
                order_id=filled.order_id,
            )
            logger.info("✓ %s %s %s %d股 @ %.2f [%s]",
                       decision.fusion_action, decision.symbol, decision.name,
                       qty, filled.filled_price or decision.price, filled.order_id)
        else:
            result = TradeResult(
                symbol=decision.symbol,
                name=decision.name,
                action=decision.fusion_action,
                quantity=0,
                price=decision.price,
                confidence=decision.fusion_confidence,
                strategy=signal.strategy_name,
                status="rejected",
                reason="风控拒绝或下单失败",
            )
            logger.info("✗ %s %s %s 被拒绝", decision.fusion_action, decision.symbol, decision.name)

        self._trade_log.append(result)
        return result

    def _get_available_capital(self) -> float:
        portfolio = self._engine.get_portfolio_status()
        cash = portfolio.get("cash", 0)
        positions_value = sum(
            p.get("quantity", 0) * p.get("entry_price", 0)
            for p in portfolio.get("positions", {}).values()
        )
        return cash

    @staticmethod
    def _strategy_label(decision: FusionDecision) -> str:
        if decision.agreeing_strategies:
            return "+".join(decision.agreeing_strategies)
        return "fusion"

    def _build_execution_report(
        self,
        position_results: list,
        trade_results: list[TradeResult],
        market_summary: dict,
        start_time: datetime,
        dry_run: bool,
    ) -> dict:
        buys = [t for t in trade_results if t.action == "BUY"]
        sells = [t for t in trade_results if t.action == "SELL"]
        filled = [t for t in trade_results if t.status == "filled"]
        rejected = [t for t in trade_results if t.status == "rejected"]

        portfolio = self._engine.get_portfolio_status()

        return {
            "timestamp": start_time.isoformat(),
            "date": start_time.strftime("%Y-%m-%d"),
            "mode": "dry_run" if dry_run else self._config.trading.mode,
            "elapsed_seconds": round((datetime.now() - start_time).total_seconds(), 1),
            "market_summary": market_summary,
            "portfolio": {
                "cash": portfolio.get("cash", 0),
                "total_equity": portfolio.get("total_equity", 0),
                "drawdown": portfolio.get("drawdown", 0),
                "positions_count": len(portfolio.get("positions", {})),
                "circuit_breaker": portfolio.get("circuit_breaker", False),
            },
            "position_checks": len(position_results),
            "trade_summary": {
                "total": len(trade_results),
                "filled": len(filled),
                "rejected": len(rejected),
                "buy_signals": len(buys),
                "sell_signals": len(sells),
            },
            "trades": [
                {
                    "symbol": t.symbol,
                    "name": t.name,
                    "action": t.action,
                    "quantity": t.quantity,
                    "price": t.price,
                    "confidence": round(t.confidence, 4),
                    "strategy": t.strategy,
                    "status": t.status,
                    "reason": t.reason,
                    "order_id": t.order_id,
                }
                for t in trade_results
            ],
        }

    def _save_report(self, report: dict):
        import json

        date_str = report["date"]
        path = self._output_dir / f"trade_report_{date_str}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("交易报告已保存: %s", path)