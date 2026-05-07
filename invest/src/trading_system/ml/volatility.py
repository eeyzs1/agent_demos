import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VolatilityForecaster:
    def __init__(self, ewma_lambda: float = 0.94, trading_days: int = 252):
        self._ewma_lambda = ewma_lambda
        self._trading_days = trading_days
        self._last_sigma: Optional[float] = None

    def forecast(
        self,
        returns: pd.Series,
        method: str = "ewma",
        horizon: int = 5,
        annualize: bool = True,
    ) -> dict:
        returns_clean = returns.dropna()
        if len(returns_clean) < 5:
            logger.warning("Insufficient returns data for volatility forecast")
            return self._empty_forecast(horizon)

        if method == "ewma":
            result = self._forecast_ewma(returns_clean, horizon)
        elif method == "garch":
            result = self._forecast_garch(returns_clean, horizon)
        elif method == "realized":
            result = self._forecast_realized(returns_clean, horizon)
        else:
            raise ValueError(f"Unknown method: {method}. Supported: ewma, garch, realized")

        if annualize:
            factor = np.sqrt(self._trading_days)
            result["current_daily_vol"] = round(result["current_daily_vol"] * factor, 6)
            for k in range(1, horizon + 1):
                result[f"forecast_vol_{k}d"] = round(result[f"forecast_vol_{k}d"] * factor, 6)

        return result

    def _forecast_ewma(self, returns: pd.Series, horizon: int) -> dict:
        ret_vals = returns.values
        sigma_sq = float(np.var(ret_vals))

        for r in ret_vals:
            sigma_sq = self._ewma_lambda * sigma_sq + (1 - self._ewma_lambda) * r ** 2

        current_vol = float(np.sqrt(sigma_sq))
        self._last_sigma = current_vol

        forecast = {"current_daily_vol": round(current_vol, 6), "method": "ewma"}
        for k in range(1, horizon + 1):
            forecast[f"forecast_vol_{k}d"] = round(current_vol, 6)

        return forecast

    def _forecast_garch(self, returns: pd.Series, horizon: int) -> dict:
        try:
            from arch import arch_model

            scaled = returns * 100
            model = arch_model(scaled, vol="Garch", p=1, q=1, dist="normal")
            result = model.fit(disp="off", show_warning=False)

            forecasts = result.forecast(horizon=horizon)
            forecast_vars = forecasts.variance.values[-1]

            daily_vol = float(np.sqrt(result.conditional_volatility[-1] / 10000))

            forecast_dict = {"current_daily_vol": round(daily_vol, 6), "method": "garch"}
            for k in range(min(horizon, len(forecast_vars))):
                f_vol = float(np.sqrt(forecast_vars[k] / 10000))
                forecast_dict[f"forecast_vol_{k+1}d"] = round(f_vol, 6)

            logger.info("GARCH forecast: current_vol=%.4f", daily_vol)
            return forecast_dict
        except Exception as e:
            logger.warning("GARCH estimation failed: %s, falling back to EWMA", e)
            return self._forecast_ewma(returns, horizon)

    def _forecast_realized(self, returns: pd.Series, horizon: int) -> dict:
        rv = float(np.sqrt(np.sum(returns.values ** 2)))
        forecast = {"current_daily_vol": round(rv, 6), "method": "realized"}
        for k in range(1, horizon + 1):
            forecast[f"forecast_vol_{k}d"] = round(rv, 6)
        return forecast

    def _empty_forecast(self, horizon: int) -> dict:
        forecast = {"current_daily_vol": 0.2, "method": "empty"}
        for k in range(1, horizon + 1):
            forecast[f"forecast_vol_{k}d"] = 0.2
        return forecast

    def check_vol_alert(
        self,
        forecast_dict: dict,
        historical_returns: pd.Series,
        percentile: float = 95,
    ) -> dict:
        hist_vol = float(historical_returns.std() * np.sqrt(self._trading_days))
        hist_threshold = float(np.percentile(
            historical_returns.rolling(20).std().dropna() * np.sqrt(self._trading_days),
            percentile,
        ))

        forecast_5d = forecast_dict.get("forecast_vol_5d", forecast_dict.get("forecast_vol_1d", 0.2))

        alert = forecast_5d > hist_threshold

        return {
            "alert_triggered": alert,
            "forecast_5d_vol": round(forecast_5d, 4),
            "historical_95pct_vol": round(hist_threshold, 4),
            "current_historical_vol": round(hist_vol, 4),
            "severity": "high" if forecast_5d > hist_threshold * 1.5 else "medium" if alert else "normal",
        }

    @property
    def last_sigma(self) -> Optional[float]:
        return self._last_sigma
