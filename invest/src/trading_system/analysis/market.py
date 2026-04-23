import numpy as np
import pandas as pd

from trading_system.strategy.base import MarketState


class MarketAnalyzer:
    @staticmethod
    def detect_state(data: pd.DataFrame, window: int = 50) -> MarketState:
        if len(data) < window:
            return MarketState.UNKNOWN

        close = data["close"].iloc[-window:]
        sma = close.rolling(window=window).mean().iloc[-1]
        current_price = close.iloc[-1]

        returns = close.pct_change().dropna()
        volatility = returns.std()

        adx = MarketAnalyzer._calculate_adx(data, period=14)

        if current_price > sma * 1.02 and adx > 25:
            return MarketState.BULL
        elif current_price < sma * 0.98 and adx > 25:
            return MarketState.BEAR
        elif adx < 20 or volatility < 0.01:
            return MarketState.RANGE
        elif current_price > sma:
            return MarketState.BULL
        else:
            return MarketState.BEAR

    @staticmethod
    def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        df["sma_5"] = df["close"].rolling(window=5).mean()
        df["sma_10"] = df["close"].rolling(window=10).mean()
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["sma_50"] = df["close"].rolling(window=50).mean()
        df["sma_200"] = df["close"].rolling(window=200).mean()

        df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        df["rsi_14"] = MarketAnalyzer._calculate_rsi(df["close"], 14)

        bb_period = 20
        bb_std = 2.0
        df["bb_mid"] = df["close"].rolling(window=bb_period).mean()
        bb_std_val = df["close"].rolling(window=bb_period).std()
        df["bb_upper"] = df["bb_mid"] + bb_std_val * bb_std
        df["bb_lower"] = df["bb_mid"] - bb_std_val * bb_std

        df["atr_14"] = MarketAnalyzer._calculate_atr(df, 14)

        df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

        df["adx_14"] = MarketAnalyzer._calculate_adx_series(df, 14)

        return df

    @staticmethod
    def analyze_symbol(data: pd.DataFrame) -> dict:
        if data.empty:
            return {"error": "No data available"}

        indicators = MarketAnalyzer.calculate_indicators(data)
        last = indicators.iloc[-1]
        state = MarketAnalyzer.detect_state(data)

        signals = []
        if not pd.isna(last.get("rsi_14")):
            if last["rsi_14"] < 30:
                signals.append("RSI超卖")
            elif last["rsi_14"] > 70:
                signals.append("RSI超买")

        if not pd.isna(last.get("macd_hist")):
            prev = indicators.iloc[-2] if len(indicators) > 1 else last
            if prev.get("macd_hist", 0) < 0 and last.get("macd_hist", 0) > 0:
                signals.append("MACD金叉")
            elif prev.get("macd_hist", 0) > 0 and last.get("macd_hist", 0) < 0:
                signals.append("MACD死叉")

        if not pd.isna(last.get("sma_5")) and not pd.isna(last.get("sma_20")):
            if last["sma_5"] > last["sma_20"]:
                signals.append("短期均线多头")
            else:
                signals.append("短期均线空头")

        return {
            "current_price": last["close"],
            "market_state": state.value,
            "rsi": round(last.get("rsi_14", 0), 2) if not pd.isna(last.get("rsi_14")) else None,
            "macd": round(last.get("macd", 0), 4) if not pd.isna(last.get("macd")) else None,
            "macd_signal": round(last.get("macd_signal", 0), 4)
            if not pd.isna(last.get("macd_signal"))
            else None,
            "atr": round(last.get("atr_14", 0), 2) if not pd.isna(last.get("atr_14")) else None,
            "adx": round(last.get("adx_14", 0), 2) if not pd.isna(last.get("adx_14")) else None,
            "volume_ratio": round(last.get("volume_ratio", 0), 2)
            if not pd.isna(last.get("volume_ratio"))
            else None,
            "bb_upper": round(last.get("bb_upper", 0), 2)
            if not pd.isna(last.get("bb_upper"))
            else None,
            "bb_lower": round(last.get("bb_lower", 0), 2)
            if not pd.isna(last.get("bb_lower"))
            else None,
            "signals": signals,
        }

    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def _calculate_adx(data: pd.DataFrame, period: int = 14) -> float:
        series = MarketAnalyzer._calculate_adx_series(data, period)
        if series.empty or pd.isna(series.iloc[-1]):
            return 0.0
        return float(series.iloc[-1])

    @staticmethod
    def _calculate_adx_series(data: pd.DataFrame, period: int = 14) -> pd.Series:
        high = data["high"]
        low = data["low"]
        close = data["close"]

        plus_dm = high.diff()
        minus_dm = low.diff().abs()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr.replace(0, np.inf))
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr.replace(0, np.inf))

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.inf)
        adx = dx.rolling(window=period).mean()

        return adx
