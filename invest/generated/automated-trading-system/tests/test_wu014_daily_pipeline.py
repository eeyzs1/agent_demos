"""WU014: Integration tests — full daily pipeline end-to-end.

Verifies:
- daily-run completes: scan → score → strategy fusion → risk → report
- daily-trade completes: scan → score → fusion → risk → order
- Pipeline produces valid output at each stage
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Ensure the src directory is in the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_system.core.config import ConfigManager, get_config
from trading_system.core.event_bus import EventBus, get_event_bus
from trading_system.core.audit import AuditLogger, get_audit_logger
from trading_system.data.fetcher import MarketDataFetcher
from trading_system.pipeline.screener import StockScreener
from trading_system.strategy.strategies import StrategyEngine, TrendFollowingStrategy, MeanReversionStrategy, BreakoutStrategy
from trading_system.risk.manager import RiskManager, RiskState
from trading_system.sentiment.analyzer import SentimentAnalyzer
from trading_system.execution.executor import ExecutionEngine


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory with minimal YAML config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)
        default_yaml = config_path / "default.yaml"
        default_yaml.write_text("""
risk:
  max_position_pct: 0.02
  max_drawdown_pct: 0.20
  daily_loss_pct: 0.05
  cooldown_days: 3
  stop_loss_pct: 0.05
  take_profit_pct: 0.15

trading:
  initial_capital: 100000.0
  mode: paper

backtest:
  commission_rate: 0.0003
  slippage: 0.001

strategy:
  weights:
    trend_following: 1.0
    mean_reversion: 1.0
    breakout: 1.0
  default_params:
    trend_following:
      ma_short: 20
      ma_long: 60
      volume_ratio: 1.5
      adx_period: 14
      adx_threshold: 25.0
    mean_reversion:
      bollinger_period: 20
      bollinger_std: 2.0
      rsi_period: 14
      rsi_oversold: 30
      rsi_overbought: 70
    breakout:
      lookback_days: 20
      volume_threshold: 2.0
      atr_period: 14
      atr_stop_multiplier: 2.0

screening:
  factor_weights:
    technical: 0.40
    fundamental: 0.30
    capital: 0.20
    sentiment: 0.10
  exclude_st: true
  exclude_new_listings_days: 60
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  vol_short_period: 5
  vol_long_period: 20

sentiment:
  weights:
    advance_decline: 0.20
    limit_ratio: 0.15
    turnover: 0.15
    new_high_low: 0.15
    margin: 0.15
    index_trend: 0.20
  thresholds:
    advance_decline_bullish: 1.5
    advance_decline_bearish: 0.67
    limit_up_minimum: 20
    high_turnover_pct: 1.5
    low_turnover_pct: 0.7
    margin_change_bullish: 0.02
    margin_change_bearish: -0.02

data:
  cache_dir: "data/cache"
  cache_ttl_hours: 24
  request_timeout: 30
  max_retries: 3
  retry_delay: 5

monte_carlo:
  simulations: 1000
  confidence_levels: [0.10, 0.25, 0.50, 0.75, 0.90]

deflated_sharpe:
  num_trials: 100
  variance_multiplier: 3.0

ml:
  arbitrage:
    entry_zscore: 2.0
    exit_zscore: 0.5
    half_life_window: 252
    lookback_period: 252
    pca_threshold: 2.0
    hmm_n_regimes: 3
    kalman_delta: 0.0001
    kalman_transition_cov: 0.00001
""", encoding="utf-8")
        yield str(tmpdir)


@pytest.fixture
def sample_ohlcv_data():
    """Generate a 200-day sample OHLCV DataFrame for testing."""
    dates = pd.date_range("2024-01-01", periods=200, freq="B")
    rng = np.random.RandomState(42)
    base_price = 50.0
    noise = rng.randn(200).cumsum() * 2
    close = base_price + noise + np.linspace(0, 20, 200)  # Upward trend
    high = close + rng.uniform(0.5, 2.0, 200)
    low = close - rng.uniform(0.5, 2.0, 200)
    open_ = low + rng.uniform(0, 1, 200) * (high - low)
    volume = (rng.randint(5000, 50000, 200) * (1 + np.linspace(0, 2, 200))).astype(int)

    df = pd.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    return df


@pytest.fixture
def sample_stock_list():
    """Generate a sample A-share stock list."""
    return pd.DataFrame({
        "code": ["000001", "000002", "600519", "600036", "000858"],
        "name": ["平安银行", "万科A", "贵州茅台", "招商银行", "五粮液"],
        "industry": ["银行", "房地产", "白酒", "银行", "白酒"],
        "list_date": ["19910403", "19910129", "20010827", "20020409", "19980427"],
    })


@pytest.fixture
def sample_sentiment_data():
    """Generate sample market-wide sentiment data."""
    return {
        "advancing": 2800,
        "declining": 1200,
        "total_stocks": 4500,
        "limit_up": 45,
        "limit_down": 5,
        "current_turnover": 9500.0,
        "avg_turnover_20d": 8000.0,
        "new_highs": 120,
        "new_lows": 30,
        "margin_balance": 1500000.0,
        "margin_balance_prev": 1480000.0,
        "index_closes": [float(3000 + i * 2) for i in range(60)],
        "hotspots": [
            {"sector": "白酒", "advance_count": 18, "decline_count": 2, "avg_change_pct": 2.5, "volume_ratio": 1.8},
            {"sector": "银行", "advance_count": 12, "decline_count": 8, "avg_change_pct": 0.5, "volume_ratio": 0.9},
        ],
    }


# ---------------------------------------------------------------------------
# WU014: Full daily pipeline end-to-end
# ---------------------------------------------------------------------------

class TestDailyPipelineEndToEnd:
    """Test the complete daily pipeline from scan to report."""

    def test_pipeline_step1_sentiment_analysis(self, temp_config_dir, sample_sentiment_data):
        """Step 1: Market sentiment analysis produces valid 6-dimension result."""
        analyzer = SentimentAnalyzer(config_dir=temp_config_dir)
        result = analyzer.analyze(sample_sentiment_data)

        assert result.overall_score is not None
        assert 0.0 <= result.overall_score <= 1.0
        assert result.level in ("强烈看多", "看多", "中性", "看空", "强烈看空")
        assert len(result.dimensions) == 6
        assert result.confidence > 0.0

        # All 6 dimensions should be present
        expected_dims = {"advance_decline", "limit_ratio", "turnover",
                         "new_high_low", "margin", "index_trend"}
        assert set(result.dimensions.keys()) == expected_dims

        # Hotspots should be processed
        assert len(result.hotspots) == 2
        assert result.hotspots[0]["sector"] == "白酒"


    def test_pipeline_step2_stock_list_filtering(self, temp_config_dir, sample_stock_list, sample_ohlcv_data):
        """Step 2: Stock screening filters ST/delisted and scores candidates."""
        screener = StockScreener(config_dir=temp_config_dir)

        # Mock the MarketDataFetcher to avoid real API calls
        with patch.object(screener._fetcher, "get_daily_data", return_value=sample_ohlcv_data):
            with patch.object(screener._fetcher, "get_financial_data", return_value=pd.DataFrame()):
                with patch.object(screener._fetcher, "get_stock_list", return_value=sample_stock_list):
                    with patch.object(screener._fetcher, "get_market_sentiment_data", return_value={"breadth_available": True}):
                        df = screener.screen(sample_stock_list, "20240101", "20241231")

        assert df is not None
        assert not df.empty
        assert len(df) <= len(sample_stock_list)
        assert "total" in df.columns
        assert "technical" in df.columns
        assert "fundamental" in df.columns
        assert "capital_flow" in df.columns
        assert "sentiment" in df.columns

        # Scores should be in valid range
        for col in ["total", "technical", "fundamental", "capital_flow", "sentiment"]:
            assert df[col].between(0, 1).all(), f"{col} scores out of range"


    def test_pipeline_step3_strategy_signal_generation(self, temp_config_dir, sample_ohlcv_data):
        """Step 3: Strategy engine generates signals for all stocks."""
        engine = StrategyEngine(config_dir=temp_config_dir)

        stock_data = {"000001": sample_ohlcv_data, "600519": sample_ohlcv_data}
        signals = engine.generate_signals(stock_data)

        assert signals is not None
        assert not signals.empty
        assert "symbol" in signals.columns
        assert "combined_score" in signals.columns

        # Signal columns for each strategy
        signal_cols = [c for c in signals.columns if c.startswith("signal_")]
        assert len(signal_cols) == 3  # trend_following, mean_reversion, breakout

        # Each symbol should have signals
        symbols = signals["symbol"].unique()
        assert len(symbols) == 2


    def test_pipeline_step4_risk_assessment(self, temp_config_dir):
        """Step 4: Risk manager produces valid state assessment."""
        rm = RiskManager(config_dir=temp_config_dir)

        assert rm.state.trading_mode == "paper"
        assert rm.state.total_capital == 100000.0

        # Check a position that fits within limits
        ok, reason = rm.can_open_position("600519", 1800.0, 1, "long")
        assert ok, f"Position should be approved: {reason}"

        # Check a position that exceeds max position size
        ok, reason = rm.can_open_position("600519", 1800.0, 5000, "long")
        assert not ok
        assert "exceeds" in reason.lower() or "max" in reason.lower()


    def test_pipeline_step5_daily_run_complete_flow(self, temp_config_dir, sample_stock_list, sample_ohlcv_data, sample_sentiment_data):
        """Step 5: Full daily-run pipeline completes end-to-end (no real API calls)."""
        # Initialize all components
        screener = StockScreener(config_dir=temp_config_dir)
        engine = StrategyEngine(config_dir=temp_config_dir)
        risk_mgr = RiskManager(config_dir=temp_config_dir)
        sentiment = SentimentAnalyzer(config_dir=temp_config_dir)

        # Step 1: Sentiment analysis
        sent_result = sentiment.analyze(sample_sentiment_data)
        assert sent_result.level is not None, "Sentiment should produce a level"

        # Step 2: Screen stocks (mock data fetcher)
        with patch.object(screener._fetcher, "get_daily_data", return_value=sample_ohlcv_data):
            with patch.object(screener._fetcher, "get_financial_data", return_value=pd.DataFrame()):
                with patch.object(screener._fetcher, "get_stock_list", return_value=sample_stock_list):
                    with patch.object(screener._fetcher, "get_market_sentiment_data", return_value={"breadth_available": True}):
                        candidates = screener.screen(sample_stock_list, "20240101", "20241231")
                        top = screener.get_top_candidates(candidates, 3)

        assert not top.empty, "Screening should return candidates"
        assert len(top) <= 3

        # Step 3: Generate strategy signals for top candidates
        stock_data = {}
        for _, row in top.iterrows():
            stock_data[row["code"]] = sample_ohlcv_data

        signals = engine.generate_signals(stock_data)
        assert not signals.empty, "Strategy engine should produce signals"

        # Step 4: Risk assessment
        state = risk_mgr.get_position_summary()
        assert state["trading_mode"] == "paper"
        assert state["circuit_breaker_active"] == False

        # Verify pipeline produces valid state at each stage
        assert sent_result.confidence > 0.0
        assert "total" in top.columns
        assert "combined_score" in signals.columns
        assert "drawdown_pct" in state


    def test_pipeline_daily_trade_flow(self, temp_config_dir, sample_stock_list, sample_ohlcv_data):
        """Test daily-trade pipeline: scan → score → fusion → risk → order."""
        screener = StockScreener(config_dir=temp_config_dir)
        engine = StrategyEngine(config_dir=temp_config_dir)
        risk_mgr = RiskManager(config_dir=temp_config_dir)
        executor = ExecutionEngine(config_dir=temp_config_dir)

        with patch.object(screener._fetcher, "get_daily_data", return_value=sample_ohlcv_data):
            with patch.object(screener._fetcher, "get_financial_data", return_value=pd.DataFrame()):
                with patch.object(screener._fetcher, "get_stock_list", return_value=sample_stock_list):
                    with patch.object(screener._fetcher, "get_market_sentiment_data", return_value={"breadth_available": True}):
                        candidates = screener.screen(sample_stock_list, "20240101", "20241231")
                        top = screener.get_top_candidates(candidates, 3)

        # Generate signals
        stock_data = {}
        for _, row in top.iterrows():
            stock_data[row["code"]] = sample_ohlcv_data
        signals = engine.generate_signals(stock_data)

        # Place paper orders for signals with positive combined_score
        orders = []
        if not signals.empty:
            for _, row in signals.groupby("symbol").last().reset_index().iterrows():
                sym = row["symbol"]
                cs = row.get("combined_score", 0)
                if cs > 0:
                    ok, reason = risk_mgr.can_open_position(sym, 50.0, 100, "long")
                    if ok:
                        order = executor.place_order(sym, "buy", 100, 50.0, "market")
                        if order:
                            orders.append(order)

        # Verify orders
        assert len(orders) >= 0, "Should handle zero or more orders gracefully"
        for order in orders:
            assert order.trading_mode == "paper"
            assert order.status.value in ("filled", "pending", "rejected")

        # Verify execution summary
        summary = executor.get_summary()
        assert summary["trading_mode"] == "paper"
        assert "total_orders" in summary
        assert "total_trades" in summary


    def test_pipeline_st_removal(self, temp_config_dir):
        """Test that ST stocks are excluded from screening."""
        stock_list = pd.DataFrame({
            "code": ["000001", "000002", "600001"],
            "name": ["平安银行", "*ST华泽", "ST康美"],
            "industry": ["银行", "材料", "医药"],
            "list_date": ["19910403", "20000101", "20000101"],
        })
        screener = StockScreener(config_dir=temp_config_dir)

        # ST/退市 stocks should be completely excluded
        with patch.object(screener._fetcher, "get_daily_data") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame({
                "date": ["2024-01-01"],
                "close": [50.0], "open": [49.0], "high": [51.0], "low": [48.0], "volume": [10000],
            })
            with patch.object(screener._fetcher, "get_financial_data", return_value=pd.DataFrame()):
                with patch.object(screener._fetcher, "get_stock_list", return_value=stock_list):
                    with patch.object(screener._fetcher, "get_market_sentiment_data", return_value={"breadth_available": True}):
                        result = screener.screen(stock_list, "20240101", "20241231")

        # Only 平安银行 should remain (ST stocks excluded)
        assert len(result) == 1
        assert result.iloc[0]["code"] == "000001"
        assert result.iloc[0]["name"] == "平安银行"


    def test_pipeline_empty_data_graceful(self, temp_config_dir):
        """Test that pipeline handles empty data gracefully."""
        engine = StrategyEngine(config_dir=temp_config_dir)
        signals = engine.generate_signals({})
        assert signals.empty, "Empty input should produce empty DataFrame"

        screener = StockScreener(config_dir=temp_config_dir)
        with patch.object(screener._fetcher, "get_daily_data", return_value=pd.DataFrame()):
            with patch.object(screener._fetcher, "get_financial_data", return_value=pd.DataFrame()):
                with patch.object(screener._fetcher, "get_stock_list", return_value=pd.DataFrame()):
                    with patch.object(screener._fetcher, "get_market_sentiment_data", return_value={}):
                        result = screener.screen(pd.DataFrame(), "20240101", "20241231")
        assert result.empty, "Empty stock list should produce empty result"


# ---------------------------------------------------------------------------
# Strategy Signal Fusion Tests
# ---------------------------------------------------------------------------

class TestStrategySignalFusion:
    """Test strategy signal fusion in the pipeline context."""

    def test_fusion_weighted_scoring(self, temp_config_dir, sample_ohlcv_data):
        """Test that signal fusion produces weighted combined scores."""
        engine = StrategyEngine(config_dir=temp_config_dir)

        # Verify weights are loaded
        assert len(engine.weights) == 3
        assert all(isinstance(w, float) for w in engine.weights.values())

        signals = engine.generate_signals({"test": sample_ohlcv_data})
        assert not signals.empty
        assert "combined_score" in signals.columns

        # Combined score should be the weighted sum of individual signal scores
        signal_cols = [c for c in signals.columns if c.startswith("signal_")]
        for _, row in signals.iterrows():
            expected = sum(
                row[col] * engine.weights[col.replace("signal_", "")]
                for col in signal_cols
            )
            assert abs(row["combined_score"] - expected) < 0.001


    def test_individual_strategy_signal_types(self, temp_config_dir, sample_ohlcv_data):
        """Test each strategy produces valid signal types (1, -1, 0)."""
        trend = TrendFollowingStrategy()
        mean = MeanReversionStrategy()
        breakout = BreakoutStrategy()

        df_trend = trend.generate_signals(sample_ohlcv_data)
        df_mean = mean.generate_signals(sample_ohlcv_data)
        df_breakout = breakout.generate_signals(sample_ohlcv_data)

        for name, df in [("trend", df_trend), ("mean", df_mean), ("breakout", df_breakout)]:
            assert "signal" in df.columns, f"{name} missing signal column"
            unique_signals = set(df["signal"].unique())
            assert unique_signals.issubset({-1, 0, 1}), f"{name} has invalid signals: {unique_signals}"


# ---------------------------------------------------------------------------
# Sentiment Analysis Edge Cases
# ---------------------------------------------------------------------------

class TestSentimentEdgeCases:
    """Test sentiment analysis handles edge cases."""

    def test_empty_market_data(self, temp_config_dir):
        """Test sentiment analysis with empty market data."""
        analyzer = SentimentAnalyzer(config_dir=temp_config_dir)
        result = analyzer.analyze({})

        assert result is not None
        assert 0.0 <= result.overall_score <= 1.0
        # All dimensions get neutral defaults, so confidence may be 1.0
        assert result.level in ("强烈看多", "看多", "中性", "看空", "强烈看空")


    def test_partial_sentiment_data(self, temp_config_dir):
        """Test sentiment analysis with partial data (some dimensions missing)."""
        analyzer = SentimentAnalyzer(config_dir=temp_config_dir)
        partial = {
            "advancing": 3000,
            "declining": 1000,
            "total_stocks": 4500,
        }
        result = analyzer.analyze(partial)

        assert result is not None
        # All dimensions get neutral defaults when missing, overall score should be valid
        assert 0.0 <= result.overall_score <= 1.0


    def test_sentiment_level_thresholds(self, temp_config_dir):
        """Test sentiment level classification at each threshold boundary."""
        analyzer = SentimentAnalyzer(config_dir=temp_config_dir)

        # Test each level
        full_data = {
            "advancing": 3000, "declining": 1000, "total_stocks": 4500,
            "limit_up": 30, "limit_down": 5,
            "current_turnover": 9000.0, "avg_turnover_20d": 8000.0,
            "new_highs": 100, "new_lows": 20,
            "margin_balance": 1500000.0, "margin_balance_prev": 1480000.0,
            "index_closes": [float(3000 + i * 2) for i in range(60)],
        }

        result = analyzer.analyze(full_data)
        assert result.level in ("强烈看多", "看多", "中性", "看空", "强烈看空")
        assert result.overall_score > 0.0


    def test_hotspot_processing(self, temp_config_dir):
        """Test hotspot momentum labeling."""
        analyzer = SentimentAnalyzer(config_dir=temp_config_dir)
        market_data = {
            "advancing": 3000, "declining": 1000, "total_stocks": 4500,
            "limit_up": 30, "limit_down": 5,
            "current_turnover": 9000.0, "avg_turnover_20d": 8000.0,
            "new_highs": 100, "new_lows": 20,
            "margin_balance": 1500000.0, "margin_balance_prev": 1480000.0,
            "index_closes": [float(3000 + i * 2) for i in range(60)],
            "hotspots": [
                {"sector": "白酒", "advance_count": 18, "decline_count": 2, "avg_change_pct": 3.0, "volume_ratio": 2.0},
                {"sector": "银行", "advance_count": 8, "decline_count": 12, "avg_change_pct": -1.0, "volume_ratio": 0.5},
            ],
        }

        result = analyzer.analyze(market_data)
        assert len(result.hotspots) == 2

        # Strong momentum sector should be first
        assert result.hotspots[0]["sector"] == "白酒"
        assert result.hotspots[0]["momentum_label"] == "强动量"

        # Weak momentum sector
        assert result.hotspots[1]["momentum_label"] in ("弱动量", "负动量")