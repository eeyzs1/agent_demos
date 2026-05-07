import logging
from typing import Optional

import numpy as np

from trading_system.core.config import RiskConfig
from trading_system.strategy.base import Signal

logger = logging.getLogger(__name__)


class PositionSizer:
    def __init__(self, config: RiskConfig, initial_capital: float):
        self._config = config
        self._initial_capital = initial_capital
        self._price_history: dict[str, list[float]] = {}
        self._vol_cache: dict[str, float] = {}

    def update_price_history(self, symbol: str, price: float) -> None:
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append(price)
        max_len = self._config.vol_lookback_days * 2
        if len(self._price_history[symbol]) > max_len:
            self._price_history[symbol] = self._price_history[symbol][-max_len:]
        self._vol_cache.pop(symbol, None)

    def estimate_volatility(self, symbol: str, close_prices: Optional[list[float]] = None) -> float:
        if symbol in self._vol_cache and close_prices is None:
            return self._vol_cache[symbol]
        prices = close_prices if close_prices is not None else self._price_history.get(symbol, [])
        lookback = self._config.vol_lookback_days
        if len(prices) < lookback + 1:
            vol = 0.20
            if close_prices is None:
                self._vol_cache[symbol] = vol
            return vol
        recent = prices[-(lookback + 1) :]
        returns = np.diff(recent) / recent[:-1]
        daily_vol = np.std(returns, ddof=1)
        annualized_vol = daily_vol * np.sqrt(252)
        if close_prices is None:
            self._vol_cache[symbol] = annualized_vol
        return annualized_vol

    def calc_vol_multiplier(
        self, symbol: str = "", close_prices: Optional[list[float]] = None
    ) -> float:
        realized_vol = self.estimate_volatility(symbol, close_prices)
        if realized_vol <= 0:
            return 1.0
        multiplier = self._config.target_volatility / realized_vol
        return min(multiplier, 1.0)

    @staticmethod
    def calc_drawdown_multiplier(current_dd: float, config: RiskConfig) -> float:
        soft = config.drawdown_soft_limit
        hard = config.drawdown_hard_limit
        if current_dd <= soft:
            return 1.0
        if current_dd >= hard:
            return 0.0
        return (hard - current_dd) / (hard - soft)

    def calculate_position_size(
        self,
        equity: float,
        signal: Signal,
        current_drawdown: float,
        close_prices: Optional[list[float]] = None,
    ) -> float:
        if signal.stop_loss is None or signal.price <= 0:
            return 0.0

        base_risk = self._config.max_risk_per_trade
        risk_amount = equity * base_risk

        risk_per_share = abs(signal.price - signal.stop_loss)
        if risk_per_share <= 0:
            return 0.0

        quantity = risk_amount / risk_per_share

        vol_mult = self.calc_vol_multiplier(signal.symbol, close_prices)
        dd_mult = self.calc_drawdown_multiplier(current_drawdown, self._config)
        conf_mult = max(signal.confidence, 0.0)

        total_mult = vol_mult * dd_mult * conf_mult
        quantity *= total_mult

        max_position_value = equity * 0.25
        max_quantity = max_position_value / signal.price
        quantity = min(quantity, max_quantity)

        quantity = int(quantity / 100) * 100
        if quantity <= 0:
            return 0.0

        logger.info(
            "Position calc: %s base=%.0f vol=%.2f dd=%.2f conf=%.2f total=%.2f qty=%.0f",
            signal.symbol,
            risk_amount,
            vol_mult,
            dd_mult,
            conf_mult,
            total_mult,
            quantity,
        )

        return float(quantity)
