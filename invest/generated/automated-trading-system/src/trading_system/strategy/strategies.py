"""Strategy engine — quantitative strategies for A-share trading.

Strategies: TrendFollowing (MA crossover + volume + ADX), MeanReversion
(Bollinger + RSI), Breakout (N-day high + volume spike + ATR stop).
StrategyEngine orchestrates and fuses signals.

All parameters from YAML config; no hardcoded values.  (AR009)
Strategy layer depends only on data and core, NOT on risk or execution.  (AR004)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.config import get_config
from ..core.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)


# ======================================================================
# Trend Following Strategy
# ======================================================================

class TrendFollowingStrategy:
    """Dual-MA crossover with volume confirmation and ADX trend filter.

    Generates buy signals (1) on golden cross with volume confirmation
    and ADX > threshold.  Generates sell signals (-1) on death cross.
    Neutral (0) otherwise.

    Attributes:
        name: Strategy identifier string.
        params: Dict of strategy parameters (ma_short, ma_long, volume_ratio, adx_period, adx_threshold).
    """

    name: str = "trend_following"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Initialise TrendFollowingStrategy with optional custom parameters.

        Args:
            params: Optional dict overriding default config values.
                Supported keys: ma_short, ma_long, volume_ratio,
                adx_period, adx_threshold.
        """
        defaults = self._load_defaults()
        self.params: Dict[str, Any] = {**defaults, **(params or {})}
        self._event_bus = get_event_bus()
        logger.info(
            "TrendFollowingStrategy initialised: ma_short=%s, ma_long=%s, vol_ratio=%s, adx=%s/%s",
            self.params.get("ma_short"),
            self.params.get("ma_long"),
            self.params.get("volume_ratio"),
            self.params.get("adx_period"),
            self.params.get("adx_threshold"),
        )

    @staticmethod
    def _load_defaults() -> Dict[str, Any]:
        """Load default parameters from configuration."""
        cfg = get_config()
        return {
            "ma_short": int(cfg.get("strategy.default_params.trend_following.ma_short", 20)),
            "ma_long": int(cfg.get("strategy.default_params.trend_following.ma_long", 60)),
            "volume_ratio": float(cfg.get("strategy.default_params.trend_following.volume_ratio", 1.5)),
            "adx_period": int(cfg.get("strategy.default_params.trend_following.adx_period", 14)),
            "adx_threshold": float(cfg.get("strategy.default_params.trend_following.adx_threshold", 25.0)),
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals from OHLCV data.

        Computes dual-MA crossover, volume confirmation, and ADX filter.
        Adds a 'signal' column (1=buy, -1=sell, 0=hold) to the DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume.
                Must have a datetime-like index or a 'date' column.

        Returns:
            A copy of the input DataFrame with additional columns:
            signal, ma_short, ma_long, adx, volume_ratio.
        """
        df = self._prepare_dataframe(df)

        if df.empty:
            logger.warning("TrendFollowingStrategy: empty DataFrame received.")
            return df

        ma_short = int(self.params["ma_short"])
        ma_long = int(self.params["ma_long"])
        vol_ratio = float(self.params["volume_ratio"])
        adx_period = int(self.params["adx_period"])
        adx_threshold = float(self.params["adx_threshold"])

        # Moving averages
        df["ma_short"] = df["close"].rolling(ma_short, min_periods=1).mean()
        df["ma_long"] = df["close"].rolling(ma_long, min_periods=1).mean()

        # Volume confirmation
        df["vol_ma"] = df["volume"].rolling(ma_short, min_periods=1).mean()
        df["volume_ratio"] = df["volume"] / df["vol_ma"].replace(0, np.nan)

        # Crossover detection
        df["cross_up"] = (df["ma_short"] > df["ma_long"]) & (df["ma_short"].shift(1) <= df["ma_long"].shift(1))
        df["cross_dn"] = (df["ma_short"] < df["ma_long"]) & (df["ma_short"].shift(1) >= df["ma_long"].shift(1))

        # ADX filter
        df["adx"] = self._compute_adx(df, adx_period)

        # Signal generation
        df["signal"] = 0
        buy_mask = df["cross_up"] & (df["volume_ratio"] >= vol_ratio) & (df["adx"] >= adx_threshold)
        sell_mask = df["cross_dn"]
        df.loc[buy_mask, "signal"] = 1
        df.loc[sell_mask, "signal"] = -1

        # Clean up intermediate columns
        df = df.drop(columns=["cross_up", "cross_dn", "vol_ma"], errors="ignore")

        # Publish event
        signal_count = int((df["signal"] != 0).sum())
        self._event_bus.publish(
            "strategy.signals_generated",
            {
                "strategy": self.name,
                "signal_count": signal_count,
                "rows": len(df),
                "timestamp": datetime.now().isoformat(),
            },
            source=f"strategy.{self.name}",
        )

        logger.debug("TrendFollowing: %d signals from %d rows", signal_count, len(df))
        return df

    def backtest(self, df: pd.DataFrame, signals: pd.DataFrame) -> List[Dict[str, Any]]:
        """Backtest signals against price data to produce a list of trades.

        A simple vectorised backtest: enters on buy signal (1), exits on
        sell signal (-1).  Does not account for slippage or commission.

        Args:
            df: Original OHLCV DataFrame with datetime index.
            signals: DataFrame with a 'signal' column (1=buy, -1=sell).
                Must share the same index as df.

        Returns:
            List of trade dicts, each with keys: entry_date, exit_date,
            entry_price, exit_price, return_pct, bars_held, signal.
        """
        trades: List[Dict[str, Any]] = []
        if df.empty or signals.empty or "signal" not in signals.columns:
            return trades

        sig = signals["signal"].fillna(0).astype(int)
        close = df["close"].astype(float)

        in_position = False
        entry_price = 0.0
        entry_date = None

        for idx in sig.index:
            if idx not in close.index:
                continue
            price = close.loc[idx]
            if np.isnan(price):
                continue

            s = sig.loc[idx]

            if s == 1 and not in_position:
                in_position = True
                entry_price = float(price)
                entry_date = idx
            elif s == -1 and in_position:
                exit_price = float(price)
                ret = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
                trades.append({
                    "entry_date": str(entry_date),
                    "exit_date": str(idx),
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "return_pct": round(ret * 100, 4),
                    "bars_held": self._count_bars(df.index, entry_date, idx),
                    "signal": self.name,
                })
                in_position = False
                entry_price = 0.0
                entry_date = None

        # Close any open position at end of data
        if in_position and entry_date is not None:
            final_price = float(close.iloc[-1])
            ret = (final_price - entry_price) / entry_price if entry_price > 0 else 0.0
            trades.append({
                "entry_date": str(entry_date),
                "exit_date": str(close.index[-1]),
                "entry_price": round(entry_price, 4),
                "exit_price": round(final_price, 4),
                "return_pct": round(ret * 100, 4),
                "bars_held": self._count_bars(df.index, entry_date, close.index[-1]),
                "signal": self.name,
            })

        logger.info("TrendFollowing backtest: %d trades", len(trades))
        return trades

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_adx(df: pd.DataFrame, period: int) -> pd.Series:
        """Compute Average Directional Index (ADX).

        Args:
            df: DataFrame with 'high', 'low', 'close' columns.
            period: ADX smoothing period.

        Returns:
            Series of ADX values, NaN for the first (2 * period) bars.
        """
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)

        # True Range
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()

        # Directional Movement
        up_move = high - high.shift(1)
        dn_move = low.shift(1) - low
        plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)

        plus_di = 100.0 * pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)
        minus_di = 100.0 * pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)

        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100.0
        adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()

        return adx.fillna(0.0)

    @staticmethod
    def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Standardise DataFrame: datetime index, required columns.

        Args:
            df: Raw OHLCV DataFrame.

        Returns:
            Standardised DataFrame copy with datetime index.
        """
        df = df.copy()
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(c.lower() for c in df.columns)
        if missing:
            logger.warning("TrendFollowing: missing columns %s, may produce NaN results.", missing)

        # Normalise column names to lowercase
        df.columns = [c.lower() for c in df.columns]

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.set_index("date").sort_index()
            else:
                logger.warning("TrendFollowing: no datetime index or 'date' column; using row order.")

        # Ensure numeric types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    @staticmethod
    def _count_bars(index: pd.Index, start, end) -> int:
        """Count the number of bars between two index values.

        Args:
            index: The DataFrame index.
            start: Start index value.
            end: End index value.

        Returns:
            Number of bars between start and end (inclusive).
        """
        try:
            start_loc = index.get_loc(start)
            end_loc = index.get_loc(end)
            if isinstance(start_loc, slice) or isinstance(end_loc, slice):
                return 0
            return abs(end_loc - start_loc) + 1
        except KeyError:
            return 0


# ======================================================================
# Mean Reversion Strategy
# ======================================================================

class MeanReversionStrategy:
    """Bollinger Bands + RSI mean reversion strategy.

    Buy (1) when price touches lower band AND RSI is oversold.
    Sell (-1) when price touches upper band AND RSI is overbought.
    Neutral (0) otherwise.

    Attributes:
        name: Strategy identifier string.
        params: Dict of strategy parameters.
    """

    name: str = "mean_reversion"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Initialise MeanReversionStrategy with optional custom parameters.

        Args:
            params: Optional dict overriding default config values.
                Supported keys: bollinger_period, bollinger_std,
                rsi_period, rsi_oversold, rsi_overbought.
        """
        defaults = self._load_defaults()
        self.params: Dict[str, Any] = {**defaults, **(params or {})}
        self._event_bus = get_event_bus()
        logger.info(
            "MeanReversionStrategy initialised: bb_period=%s, bb_std=%s, rsi=%s/%s/%s",
            self.params.get("bollinger_period"),
            self.params.get("bollinger_std"),
            self.params.get("rsi_period"),
            self.params.get("rsi_oversold"),
            self.params.get("rsi_overbought"),
        )

    @staticmethod
    def _load_defaults() -> Dict[str, Any]:
        """Load default parameters from configuration."""
        cfg = get_config()
        return {
            "bollinger_period": int(cfg.get("strategy.default_params.mean_reversion.bollinger_period", 20)),
            "bollinger_std": float(cfg.get("strategy.default_params.mean_reversion.bollinger_std", 2.0)),
            "rsi_period": int(cfg.get("strategy.default_params.mean_reversion.rsi_period", 14)),
            "rsi_oversold": int(cfg.get("strategy.default_params.mean_reversion.rsi_oversold", 30)),
            "rsi_overbought": int(cfg.get("strategy.default_params.mean_reversion.rsi_overbought", 70)),
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals from OHLCV data.

        Computes Bollinger Bands and RSI.  Buy when price at/below lower
        band and RSI oversold; sell when price at/above upper band and
        RSI overbought.

        Args:
            df: DataFrame with columns: open, high, low, close, volume.
                Must have a datetime-like index or a 'date' column.

        Returns:
            A copy of the input DataFrame with additional columns:
            signal, bb_upper, bb_lower, rsi.
        """
        df = self._prepare_dataframe(df)

        if df.empty:
            logger.warning("MeanReversionStrategy: empty DataFrame received.")
            return df

        bb_period = int(self.params["bollinger_period"])
        bb_std = float(self.params["bollinger_std"])
        rsi_period = int(self.params["rsi_period"])
        rsi_os = int(self.params["rsi_oversold"])
        rsi_ob = int(self.params["rsi_overbought"])

        close = df["close"]

        # Bollinger Bands
        df["bb_mid"] = close.rolling(bb_period, min_periods=1).mean()
        roll_std = close.rolling(bb_period, min_periods=1).std().fillna(0.0)
        df["bb_upper"] = df["bb_mid"] + bb_std * roll_std
        df["bb_lower"] = df["bb_mid"] - bb_std * roll_std

        # RSI
        df["rsi"] = self._compute_rsi(close, rsi_period)

        # Signal generation
        df["signal"] = 0
        buy_mask = (close <= df["bb_lower"]) & (df["rsi"] <= rsi_os)
        sell_mask = (close >= df["bb_upper"]) & (df["rsi"] >= rsi_ob)
        df.loc[buy_mask, "signal"] = 1
        df.loc[sell_mask, "signal"] = -1

        # Clean up
        df = df.drop(columns=["bb_mid"], errors="ignore")

        # Publish event
        signal_count = int((df["signal"] != 0).sum())
        self._event_bus.publish(
            "strategy.signals_generated",
            {
                "strategy": self.name,
                "signal_count": signal_count,
                "rows": len(df),
                "timestamp": datetime.now().isoformat(),
            },
            source=f"strategy.{self.name}",
        )

        logger.debug("MeanReversion: %d signals from %d rows", signal_count, len(df))
        return df

    def backtest(self, df: pd.DataFrame, signals: pd.DataFrame) -> List[Dict[str, Any]]:
        """Backtest signals against price data to produce a list of trades.

        Enters on buy (1), exits on sell (-1).  Mean reversion trades
        typically have shorter holding periods.

        Args:
            df: Original OHLCV DataFrame with datetime index.
            signals: DataFrame with a 'signal' column (1=buy, -1=sell).
                Must share the same index as df.

        Returns:
            List of trade dicts, each with keys: entry_date, exit_date,
            entry_price, exit_price, return_pct, bars_held, signal.
        """
        trades: List[Dict[str, Any]] = []
        if df.empty or signals.empty or "signal" not in signals.columns:
            return trades

        sig = signals["signal"].fillna(0).astype(int)
        close = df["close"].astype(float)

        in_position = False
        entry_price = 0.0
        entry_date = None

        for idx in sig.index:
            if idx not in close.index:
                continue
            price = close.loc[idx]
            if np.isnan(price):
                continue

            s = sig.loc[idx]

            if s == 1 and not in_position:
                in_position = True
                entry_price = float(price)
                entry_date = idx
            elif s == -1 and in_position:
                exit_price = float(price)
                ret = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
                trades.append({
                    "entry_date": str(entry_date),
                    "exit_date": str(idx),
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "return_pct": round(ret * 100, 4),
                    "bars_held": self._count_bars(df.index, entry_date, idx),
                    "signal": self.name,
                })
                in_position = False
                entry_price = 0.0
                entry_date = None

        if in_position and entry_date is not None:
            final_price = float(close.iloc[-1])
            ret = (final_price - entry_price) / entry_price if entry_price > 0 else 0.0
            trades.append({
                "entry_date": str(entry_date),
                "exit_date": str(close.index[-1]),
                "entry_price": round(entry_price, 4),
                "exit_price": round(final_price, 4),
                "return_pct": round(ret * 100, 4),
                "bars_held": self._count_bars(df.index, entry_date, close.index[-1]),
                "signal": self.name,
            })

        logger.info("MeanReversion backtest: %d trades", len(trades))
        return trades

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
        """Compute Relative Strength Index (RSI) using Wilder's smoothing.

        Args:
            close: Series of closing prices.
            period: RSI lookback period.

        Returns:
            Series of RSI values (0-100), 50.0 for periods with no data.
        """
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    @staticmethod
    def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Standardise DataFrame: datetime index, required columns.

        Args:
            df: Raw OHLCV DataFrame.

        Returns:
            Standardised DataFrame copy with datetime index.
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        if not isinstance(df.index, pd.DatetimeIndex):
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.set_index("date").sort_index()

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    @staticmethod
    def _count_bars(index: pd.Index, start, end) -> int:
        """Count bars between two index values."""
        try:
            return abs(index.get_loc(end) - index.get_loc(start)) + 1
        except KeyError:
            return 0


# ======================================================================
# Breakout Strategy
# ======================================================================

class BreakoutStrategy:
    """N-day high breakout with volume confirmation and ATR-based stop.

    Buy (1) when price breaks above N-day high with volume surge.
    Sell (-1) when price falls below N-day low (support breakdown).
    Neutral (0) otherwise.

    Attributes:
        name: Strategy identifier string.
        params: Dict of strategy parameters.
    """

    name: str = "breakout"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Initialise BreakoutStrategy with optional custom parameters.

        Args:
            params: Optional dict overriding default config values.
                Supported keys: lookback_days, volume_threshold,
                atr_period, atr_stop_multiplier.
        """
        defaults = self._load_defaults()
        self.params: Dict[str, Any] = {**defaults, **(params or {})}
        self._event_bus = get_event_bus()
        logger.info(
            "BreakoutStrategy initialised: lookback=%s, vol_thresh=%s, atr=%s/%s",
            self.params.get("lookback_days"),
            self.params.get("volume_threshold"),
            self.params.get("atr_period"),
            self.params.get("atr_stop_multiplier"),
        )

    @staticmethod
    def _load_defaults() -> Dict[str, Any]:
        """Load default parameters from configuration."""
        cfg = get_config()
        return {
            "lookback_days": int(cfg.get("strategy.default_params.breakout.lookback_days", 20)),
            "volume_threshold": float(cfg.get("strategy.default_params.breakout.volume_threshold", 2.0)),
            "atr_period": int(cfg.get("strategy.default_params.breakout.atr_period", 14)),
            "atr_stop_multiplier": float(cfg.get("strategy.default_params.breakout.atr_stop_multiplier", 2.0)),
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals from OHLCV data.

        Computes N-day high/low, volume ratio, and ATR.  Buy when price
        breaks the N-day high with volume confirmation; sell when price
        breaks below the N-day low.

        Args:
            df: DataFrame with columns: open, high, low, close, volume.
                Must have a datetime-like index or a 'date' column.

        Returns:
            A copy of the input DataFrame with additional columns:
            signal, n_day_high, n_day_low, atr, atr_stop_long, atr_stop_short.
        """
        df = self._prepare_dataframe(df)

        if df.empty:
            logger.warning("BreakoutStrategy: empty DataFrame received.")
            return df

        lookback = int(self.params["lookback_days"])
        vol_thresh = float(self.params["volume_threshold"])
        atr_period = int(self.params["atr_period"])
        atr_mult = float(self.params["atr_stop_multiplier"])

        # N-day high / low
        df["n_day_high"] = df["high"].rolling(lookback, min_periods=1).max()
        df["n_day_low"] = df["low"].rolling(lookback, min_periods=1).min()

        # Volume confirmation
        df["vol_ma"] = df["volume"].rolling(lookback, min_periods=1).mean()
        df["volume_ratio"] = df["volume"] / df["vol_ma"].replace(0, np.nan)

        # Breakout detection
        df["break_up"] = df["close"] >= df["n_day_high"].shift(1)
        df["vol_spike"] = df["volume_ratio"] >= vol_thresh
        df["break_dn"] = df["close"] < df["n_day_low"].shift(1)

        # ATR
        df["atr"] = self._compute_atr(df, atr_period)

        # ATR-based trailing stop levels
        df["atr_stop_long"] = df["close"] - atr_mult * df["atr"]
        df["atr_stop_short"] = df["close"] + atr_mult * df["atr"]

        # Signal generation
        df["signal"] = 0
        df.loc[df["break_up"] & df["vol_spike"], "signal"] = 1
        df.loc[df["break_dn"], "signal"] = -1

        # Clean up intermediate columns
        df = df.drop(columns=["break_up", "vol_spike", "break_dn", "vol_ma", "volume_ratio"], errors="ignore")

        # Publish event
        signal_count = int((df["signal"] != 0).sum())
        self._event_bus.publish(
            "strategy.signals_generated",
            {
                "strategy": self.name,
                "signal_count": signal_count,
                "rows": len(df),
                "timestamp": datetime.now().isoformat(),
            },
            source=f"strategy.{self.name}",
        )

        logger.debug("Breakout: %d signals from %d rows", signal_count, len(df))
        return df

    def backtest(self, df: pd.DataFrame, signals: pd.DataFrame) -> List[Dict[str, Any]]:
        """Backtest signals against price data with ATR-based stop logic.

        Enters on buy (1), exits on either sell signal (-1) or ATR-based
        stop breach.  For long positions, exits if price drops below
        atr_stop_long; for short positions, exits if price rises above
        atr_stop_short.

        Args:
            df: Original OHLCV DataFrame with datetime index.
            signals: DataFrame with 'signal' column plus 'atr_stop_long'
                and 'atr_stop_short' columns from generate_signals.

        Returns:
            List of trade dicts, each with keys: entry_date, exit_date,
            entry_price, exit_price, return_pct, bars_held, exit_reason,
            signal.
        """
        trades: List[Dict[str, Any]] = []
        required_cols = {"signal", "atr_stop_long", "atr_stop_short"}
        if df.empty or signals.empty or not required_cols.issubset(signals.columns):
            return trades

        sig = signals["signal"].fillna(0).astype(int)
        close = df["close"].astype(float)
        low = df["low"].astype(float) if "low" in df.columns else close
        high = df["high"].astype(float) if "high" in df.columns else close

        in_position = False
        position_type = 0  # 1=long, -1=short
        entry_price = 0.0
        entry_date = None
        stop_level = 0.0

        for idx in sig.index:
            if idx not in close.index:
                continue
            price = close.loc[idx]
            if np.isnan(price):
                continue

            s = sig.loc[idx]
            price_low = low.loc[idx] if not np.isnan(low.loc[idx]) else price
            price_high = high.loc[idx] if not np.isnan(high.loc[idx]) else price

            if in_position:
                exit_reason = None
                exit_price = price

                if position_type == 1:
                    # Long position: check ATR stop
                    stop = signals.loc[idx, "atr_stop_long"] if "atr_stop_long" in signals.columns else 0.0
                    if not np.isnan(stop) and price_low <= stop:
                        exit_price = stop
                        exit_reason = "atr_stop"
                    elif s == -1:
                        exit_reason = "signal"
                elif position_type == -1:
                    # Short position: check ATR stop
                    stop = signals.loc[idx, "atr_stop_short"] if "atr_stop_short" in signals.columns else float("inf")
                    if not np.isnan(stop) and price_high >= stop:
                        exit_price = stop
                        exit_reason = "atr_stop"
                    elif s == 1:
                        exit_reason = "signal"

                if exit_reason is not None:
                    ret = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
                    if position_type == -1:
                        ret = -ret  # Profit on short when price falls
                    trades.append({
                        "entry_date": str(entry_date),
                        "exit_date": str(idx),
                        "entry_price": round(entry_price, 4),
                        "exit_price": round(float(exit_price), 4),
                        "return_pct": round(ret * 100, 4),
                        "bars_held": self._count_bars(df.index, entry_date, idx),
                        "exit_reason": exit_reason,
                        "signal": self.name,
                        "position_type": "long" if position_type == 1 else "short",
                    })
                    in_position = False
                    position_type = 0
                    entry_price = 0.0
                    entry_date = None

            if not in_position:
                if s == 1:
                    in_position = True
                    position_type = 1
                    entry_price = float(price)
                    entry_date = idx
                elif s == -1:
                    in_position = True
                    position_type = -1
                    entry_price = float(price)
                    entry_date = idx

        # Close any open position at end of data
        if in_position and entry_date is not None:
            final_price = float(close.iloc[-1])
            ret = (final_price - entry_price) / entry_price if entry_price > 0 else 0.0
            if position_type == -1:
                ret = -ret
            trades.append({
                "entry_date": str(entry_date),
                "exit_date": str(close.index[-1]),
                "entry_price": round(entry_price, 4),
                "exit_price": round(final_price, 4),
                "return_pct": round(ret * 100, 4),
                "bars_held": self._count_bars(df.index, entry_date, close.index[-1]),
                "exit_reason": "end_of_data",
                "signal": self.name,
                "position_type": "long" if position_type == 1 else "short",
            })

        logger.info("Breakout backtest: %d trades", len(trades))
        return trades

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_atr(df: pd.DataFrame, period: int) -> pd.Series:
        """Compute Average True Range (ATR) using Wilder's smoothing.

        Args:
            df: DataFrame with 'high', 'low', 'close' columns.
            period: ATR smoothing period.

        Returns:
            Series of ATR values.
        """
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
        return atr.fillna(0.0)

    @staticmethod
    def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Standardise DataFrame: datetime index, required columns.

        Args:
            df: Raw OHLCV DataFrame.

        Returns:
            Standardised DataFrame copy with datetime index.
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        if not isinstance(df.index, pd.DatetimeIndex):
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.set_index("date").sort_index()

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    @staticmethod
    def _count_bars(index: pd.Index, start, end) -> int:
        """Count bars between two index values."""
        try:
            return abs(index.get_loc(end) - index.get_loc(start)) + 1
        except KeyError:
            return 0


# ======================================================================
# Strategy Engine — orchestrator & signal fusion
# ======================================================================

class StrategyEngine:
    """Orchestrates multiple strategies and fuses their signals via weighted sum.

    Runs all registered strategies on each stock's data and combines
    signals into a unified 'combined_score'.  Publishes events on start
    and completion of signal generation.

    Attributes:
        strategies: Dict mapping strategy name -> strategy instance.
        weights: Dict mapping strategy name -> fusion weight (from config).
    """

    def __init__(self, config_dir: str = "config") -> None:
        """Initialise StrategyEngine with all registered strategies.

        Args:
            config_dir: Path to configuration directory.
        """
        cfg = get_config(config_dir)
        self._event_bus = get_event_bus()

        # Instantiate strategies with default params
        self.strategies: Dict[str, Any] = {
            TrendFollowingStrategy.name: TrendFollowingStrategy(),
            MeanReversionStrategy.name: MeanReversionStrategy(),
            BreakoutStrategy.name: BreakoutStrategy(),
        }

        # Load fusion weights from config
        strategy_weights = cfg.get("strategy.weights", {})
        self.weights: Dict[str, float] = {
            name: float(strategy_weights.get(name, 1.0)) for name in self.strategies
        }

        logger.info(
            "StrategyEngine ready: strategies=%s, weights=%s",
            list(self.strategies.keys()),
            self.weights,
        )

    def generate_signals(self, stock_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Run all strategies on every stock, fuse signals, return combined DataFrame.

        Args:
            stock_data: Dict mapping stock symbol to OHLCV DataFrame.
                Each DataFrame must have datetime index and columns:
                open, high, low, close, volume.

        Returns:
            DataFrame with columns: date, symbol, signal_<strategy_name>,
            combined_score.  Returns empty DataFrame with expected columns
            if no signals are generated.
        """
        all_frames: List[pd.DataFrame] = []
        self._event_bus.publish(
            "strategy.signals_start",
            {"symbols": len(stock_data)},
            source="strategy.engine",
        )

        for symbol, df in stock_data.items():
            if df is None or df.empty:
                logger.debug("Skipping %s: empty DataFrame", symbol)
                continue

            signals: Dict[str, pd.Series] = {}
            for name, strategy in self.strategies.items():
                try:
                    result = strategy.generate_signals(df)
                    sig_col = "signal"
                    if sig_col in result.columns:
                        signals[name] = result[sig_col]
                except Exception:
                    logger.exception(
                        "Strategy %s failed for %s", name, symbol
                    )
                    continue

            if not signals:
                continue

            fused = self._fusion_signals(signals)
            fused["symbol"] = symbol
            fused["date"] = df.index
            all_frames.append(fused)

        if not all_frames:
            logger.warning("No signals generated — empty stock_data or all strategies failed.")
            self._event_bus.publish(
                "strategy.signals_complete",
                {"symbols": 0, "rows": 0},
                source="strategy.engine",
            )
            return pd.DataFrame(columns=["date", "symbol", "combined_score"])

        combined = pd.concat(all_frames, ignore_index=True)
        signal_cols = [c for c in combined.columns if c.startswith("signal_")]
        combined = combined[["date", "symbol"] + signal_cols + ["combined_score"]]

        self._event_bus.publish(
            "strategy.signals_complete",
            {"symbols": len(all_frames), "rows": len(combined)},
            source="strategy.engine",
        )
        logger.info(
            "StrategyEngine signals: %d symbols, %d rows.",
            len(all_frames),
            len(combined),
        )
        return combined

    def _fusion_signals(self, signals: Dict[str, pd.Series]) -> pd.DataFrame:
        """Weighted fusion of per-strategy signal series into combined_score.

        Args:
            signals: Dict mapping strategy_name -> signal Series (1/-1/0).

        Returns:
            DataFrame with signal_<name> columns and combined_score.
        """
        result = pd.DataFrame(index=next(iter(signals.values())).index)
        weighted = pd.Series(0.0, index=result.index)

        for name, series in signals.items():
            col_name = f"signal_{name}"
            result[col_name] = series.fillna(0).astype(int)
            weighted += result[col_name].astype(float) * self.weights.get(name, 1.0)

        result["combined_score"] = weighted.round(4)
        return result