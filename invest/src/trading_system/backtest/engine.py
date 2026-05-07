from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from trading_system.ashare.calculator import BoardType, clamp_price, detect_board_type
from trading_system.ashare.cost_model import AShareCostCalculator
from trading_system.core.config import RiskConfig
from trading_system.risk.manager import Position
from trading_system.risk.sizer import PositionSizer
from trading_system.strategy.base import PositionSide, Signal, SignalType, StrategyBase


@dataclass
class BacktestTrade:
    symbol: str
    side: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    r_multiple: float
    exit_reason: str
    strategy_name: str
    holding_days: int = 0


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    dates: list[datetime] = field(default_factory=list)
    position_sizes: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)
    vol_multipliers: list[float] = field(default_factory=list)
    dd_multipliers: list[float] = field(default_factory=list)
    t1_blocked_count: int = 0
    total_buy_commission: float = 0.0
    total_sell_commission: float = 0.0
    total_stamp_tax: float = 0.0
    total_transfer_fee: float = 0.0
    limit_price_clamped_count: int = 0
    benchmark: Optional[dict] = None

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if t.pnl > 0]

    @property
    def losing_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if t.pnl <= 0]

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return len(self.winning_trades) / len(self.trades)

    @property
    def avg_win(self) -> float:
        wins = self.winning_trades
        if not wins:
            return 0.0
        return np.mean([t.pnl_pct for t in wins])

    @property
    def avg_loss(self) -> float:
        losses = self.losing_trades
        if not losses:
            return 0.0
        return np.mean([abs(t.pnl_pct) for t in losses])

    @property
    def risk_reward_ratio(self) -> float:
        avg_l = self.avg_loss
        if avg_l <= 0:
            return 0.0
        return self.avg_win / avg_l

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for val in self.equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def max_consecutive_losses(self) -> int:
        max_streak = 0
        current_streak = 0
        for t in self.trades:
            if t.pnl <= 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak

    @property
    def avg_r_multiple(self) -> float:
        if not self.trades:
            return 0.0
        return np.mean([t.r_multiple for t in self.trades])

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def total_return_pct(self) -> float:
        if not self.equity_curve or self.equity_curve[0] <= 0:
            return 0.0
        return (self.equity_curve[-1] - self.equity_curve[0]) / self.equity_curve[0]

    @property
    def annualized_return(self) -> float:
        if not self.dates or len(self.dates) < 2:
            return 0.0
        days = (self.dates[-1] - self.dates[0]).days
        if days <= 0:
            return 0.0
        total_ret = self.total_return_pct
        return (1 + total_ret) ** (365 / days) - 1

    @property
    def ashare_summary(self) -> dict:
        total_cost = self.total_buy_commission + self.total_sell_commission + self.total_stamp_tax + self.total_transfer_fee
        gross_pnl = self.total_pnl + total_cost
        return {
            "t1_blocked_count": self.t1_blocked_count,
            "limit_price_clamped_count": self.limit_price_clamped_count,
            "total_buy_commission": round(self.total_buy_commission, 2),
            "total_sell_commission": round(self.total_sell_commission, 2),
            "total_stamp_tax": round(self.total_stamp_tax, 2),
            "total_transfer_fee": round(self.total_transfer_fee, 2),
            "total_cost": round(total_cost, 2),
            "gross_pnl_before_cost": round(gross_pnl, 2),
            "net_pnl_after_cost": round(self.total_pnl, 2),
            "cost_impact_pct": round(total_cost / abs(gross_pnl) * 100, 2) if gross_pnl != 0 else 0,
        }

    @property
    def sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        returns = pd.Series(self.equity_curve).pct_change().dropna()
        if returns.std() == 0:
            return 0.0
        return (returns.mean() / returns.std()) * np.sqrt(252)

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.winning_trades)
        gross_loss = sum(abs(t.pnl) for t in self.losing_trades)
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def exit_reason_breakdown(self) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for t in self.trades:
            breakdown[t.exit_reason] = breakdown.get(t.exit_reason, 0) + 1
        return breakdown

    @property
    def avg_holding_days(self) -> float:
        if not self.trades:
            return 0.0
        return np.mean([t.holding_days for t in self.trades])

    def get_seven_metrics(self, initial_capital: float) -> dict:
        risk_per_trade = 0.0
        if self.trades and initial_capital > 0:
            risk_amounts = []
            for t in self.trades:
                risk = abs(t.entry_price * 0.05) * t.quantity
                risk_amounts.append(risk / initial_capital)
            risk_per_trade = np.mean(risk_amounts) if risk_amounts else 0.0

        return {
            "win_rate": round(self.win_rate, 4),
            "risk_reward_ratio": round(self.risk_reward_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "risk_per_trade_pct": round(risk_per_trade, 4),
            "annualized_return": round(self.annualized_return, 4),
            "max_consecutive_losses": self.max_consecutive_losses,
            "avg_r_multiple": round(self.avg_r_multiple, 4),
        }

    def summary(self, initial_capital: float) -> dict:
        metrics = self.get_seven_metrics(initial_capital)
        return {
            "seven_key_metrics": metrics,
            "total_trades": self.total_trades,
            "winning_trades": len(self.winning_trades),
            "losing_trades": len(self.losing_trades),
            "total_pnl": round(self.total_pnl, 2),
            "total_return_pct": round(self.total_return_pct * 100, 2),
            "annualized_return_pct": round(self.annualized_return * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "profit_factor": round(self.profit_factor, 4),
            "avg_win_pct": round(self.avg_win * 100, 2),
            "avg_loss_pct": round(self.avg_loss * 100, 2),
            "final_equity": round(self.equity_curve[-1], 2)
            if self.equity_curve
            else initial_capital,
            "exit_reason_breakdown": self.exit_reason_breakdown,
            "avg_holding_days": round(self.avg_holding_days, 1),
        }


class BacktestEngine:
    def __init__(
        self,
        strategy: StrategyBase,
        initial_capital: float = 100000.0,
        risk_config: Optional[RiskConfig] = None,
        commission_rate: float = 0.0003,
        slippage_pct: float = 0.001,
        enable_limit_price: bool = True,
        cost_calculator: Optional[AShareCostCalculator] = None,
        use_open_for_signal: bool = True,
    ):
        self._strategy = strategy
        self._initial_capital = initial_capital
        self._risk_config = risk_config or RiskConfig()
        self._commission_rate = commission_rate
        self._slippage_pct = slippage_pct
        self._enable_limit_price = enable_limit_price
        self._cost_calc = cost_calculator or AShareCostCalculator()
        self._sizer = PositionSizer(self._risk_config, initial_capital)
        self._use_open_for_signal = use_open_for_signal

    def _calc_vol_multiplier(self, close_prices: list[float]) -> float:
        return self._sizer.calc_vol_multiplier(close_prices=close_prices)

    def _calc_drawdown_multiplier(self, current_dd: float) -> float:
        return PositionSizer.calc_drawdown_multiplier(current_dd, self._risk_config)

    def _calc_position_size(
        self,
        equity: float,
        signal: Signal,
        vol_mult: float,
        dd_mult: float,
    ) -> float:
        return self._sizer.calculate_position_size(
            equity=equity,
            signal=signal,
            current_drawdown=0.0,
            close_prices=None,
        )

    def _check_exit_conditions(
        self, pos: Position, high: float, low: float, date: pd.Timestamp, result: Optional[BacktestResult] = None
    ) -> Optional[tuple[str, float]]:
        if pos.is_t1_locked_on(date.to_pydatetime()):
            if result is not None:
                result.t1_blocked_count += 1
            return None

        for check_fn in [self._check_trailing_stop, self._check_stop_loss,
                         self._check_take_profit, self._check_timeout]:
            exit_result = check_fn(pos, high, low, date)
            if exit_result:
                return exit_result

        return None

    def _check_trailing_stop(
        self, pos: Position, high: float, low: float, date: pd.Timestamp
    ) -> Optional[tuple[str, float]]:
        if pos.trailing_stop is None:
            return None
        if pos.side == PositionSide.LONG and low <= pos.trailing_stop:
            return "trailing_stop", pos.trailing_stop * (1 - self._slippage_pct)
        return None

    def _check_stop_loss(
        self, pos: Position, high: float, low: float, date: pd.Timestamp
    ) -> Optional[tuple[str, float]]:
        if pos.side == PositionSide.LONG and low <= pos.stop_loss:
            return "stop_loss", pos.stop_loss * (1 - self._slippage_pct)
        return None

    def _check_take_profit(
        self, pos: Position, high: float, low: float, date: pd.Timestamp
    ) -> Optional[tuple[str, float]]:
        if pos.side == PositionSide.LONG and high >= pos.take_profit:
            return "take_profit", pos.take_profit * (1 - self._slippage_pct)
        return None

    def _check_timeout(
        self, pos: Position, high: float, low: float, date: pd.Timestamp
    ) -> Optional[tuple[str, float]]:
        holding_days = pos.holding_days_at(date.to_pydatetime())
        if holding_days >= pos.max_holding_days:
            close_ref = low if pos.side == PositionSide.LONG else high
            slip = 1 - self._slippage_pct if pos.side == PositionSide.LONG else 1 + self._slippage_pct
            return "timeout", close_ref * slip
        return None

    def run(self, data: pd.DataFrame, symbol: str = "") -> BacktestResult:
        result = BacktestResult()
        equity = self._initial_capital
        peak_equity = equity
        positions: dict[str, Position] = {}
        close_history: list[float] = []
        prev_close: Optional[float] = None
        board_type = detect_board_type(symbol) if symbol else BoardType.MAIN

        signals = self._strategy.generate_signals(data)
        signal_map: dict[pd.Timestamp, list[Signal]] = {}
        for sig in signals:
            ts = pd.Timestamp(sig.timestamp).floor("D")
            if ts not in signal_map:
                signal_map[ts] = []
            sig.symbol = symbol
            signal_map[ts].append(sig)

        for date, row in data.iterrows():
            if not isinstance(date, pd.Timestamp):
                date = pd.Timestamp(date)

            current_price = row["close"]
            high = row.get("high", current_price)
            low = row.get("low", current_price)
            close_history.append(current_price)

            if self._enable_limit_price and prev_close is not None:
                clamped_high = clamp_price(high, prev_close, board_type)
                clamped_low = clamp_price(low, prev_close, board_type)
                high = min(high, clamped_high)
                low = max(low, clamped_low)

            vol_mult = self._calc_vol_multiplier(close_history)
            current_dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
            dd_mult = self._calc_drawdown_multiplier(current_dd)

            closed_today = []
            for sym, pos in list(positions.items()):
                pos.update_trailing_stop(current_price)

                exit_result = self._check_exit_conditions(pos, high, low, date, result)
                if exit_result:
                    reason, exit_price = exit_result
                    pnl, r_mult = self._calc_pnl(pos, exit_price)
                    holding_days = pos.holding_days_at(date.to_pydatetime())
                    trade = BacktestTrade(
                        symbol=sym,
                        side=pos.side,
                        entry_date=pos.entry_time,
                        exit_date=date,
                        entry_price=pos.entry_price,
                        exit_price=exit_price,
                        quantity=pos.quantity,
                        pnl=pnl,
                        pnl_pct=pnl / pos.current_value if pos.current_value > 0 else 0,
                        r_multiple=r_mult,
                        exit_reason=reason,
                        strategy_name=pos.strategy_name,
                        holding_days=holding_days,
                    )
                    result.trades.append(trade)
                    closed_today.append(sym)

            for sym in closed_today:
                pos = positions.pop(sym)
                equity += pos.unrealized_pnl(current_price)

            if date in signal_map:
                for sig in signal_map[date]:
                    if sig.signal_type == SignalType.BUY and symbol not in positions:
                        quantity = self._calc_position_size(equity, sig, vol_mult, dd_mult)
                        if quantity <= 0:
                            continue

                        if self._use_open_for_signal and "open" in row:
                            entry_price = row["open"] * (1 + self._slippage_pct)
                        else:
                            entry_price = sig.price * (1 + self._slippage_pct)
                        if self._enable_limit_price and prev_close is not None:
                            entry_price = clamp_price(entry_price, prev_close, board_type)
                        buy_cost = self._cost_calc.calc_buy_cost(entry_price, quantity)
                        commission = buy_cost.total_cost
                        result.total_buy_commission += buy_cost.commission
                        result.total_stamp_tax += buy_cost.stamp_tax
                        result.total_transfer_fee += buy_cost.transfer_fee

                        positions[symbol] = Position(
                            symbol=symbol,
                            side=PositionSide.LONG,
                            quantity=quantity,
                            entry_price=entry_price,
                            stop_loss=sig.stop_loss or entry_price * 0.95,
                            take_profit=sig.take_profit or entry_price * 1.15,
                            entry_time=date.to_pydatetime(),
                            strategy_name=sig.strategy_name,
                            risk_amount=abs(entry_price - (sig.stop_loss or entry_price * 0.95))
                            * quantity,
                            trailing_stop=None,
                            highest_price=entry_price,
                            lowest_price=float("inf"),
                            trailing_stop_pct=self._risk_config.trailing_stop_pct,
                            trailing_stop_activate_pct=self._risk_config.trailing_stop_activate_pct,
                            max_holding_days=self._risk_config.max_holding_days,
                            commission=commission,
                            is_t1_locked=True,
                        )

                    elif sig.signal_type == SignalType.SELL:
                        if symbol not in positions:
                            continue
                        pos = positions.get(symbol)
                        if pos is None or pos.side != PositionSide.LONG:
                            continue
                        if pos.is_t1_locked_on(date.to_pydatetime()):
                            result.t1_blocked_count += 1
                            continue
                        pos = positions.pop(symbol)
                        if self._use_open_for_signal and "open" in row:
                            exit_price = row["open"] * (1 - self._slippage_pct)
                        else:
                            exit_price = sig.price * (1 - self._slippage_pct)
                        if self._enable_limit_price and prev_close is not None:
                            exit_price = clamp_price(exit_price, prev_close, board_type)
                        sell_cost = self._cost_calc.calc_sell_cost(exit_price, pos.quantity)
                        commission = sell_cost.total_cost
                        result.total_sell_commission += sell_cost.commission
                        result.total_stamp_tax += sell_cost.stamp_tax
                        result.total_transfer_fee += sell_cost.transfer_fee
                        pnl = (
                            (exit_price - pos.entry_price) * pos.quantity
                            - pos.commission
                            - commission
                        )
                        risk = pos.risk_amount if pos.risk_amount > 0 else 1
                        r_mult = pnl / risk
                        holding_days = pos.holding_days_at(date.to_pydatetime())

                        trade = BacktestTrade(
                            symbol=symbol,
                            side=pos.side,
                            entry_date=pos.entry_time,
                            exit_date=date,
                            entry_price=pos.entry_price,
                            exit_price=exit_price,
                            quantity=pos.quantity,
                            pnl=pnl,
                            pnl_pct=pnl / pos.current_value if pos.current_value > 0 else 0,
                            r_multiple=r_mult,
                            exit_reason="signal",
                            strategy_name=pos.strategy_name,
                            holding_days=holding_days,
                        )
                        result.trades.append(trade)
                        equity += pnl

            position_value = sum(p.unrealized_pnl(current_price) for p in positions.values())
            total_equity = equity + position_value
            if total_equity > peak_equity:
                peak_equity = total_equity

            result.equity_curve.append(total_equity)
            result.dates.append(date)
            result.position_sizes.append(sum(p.current_value for p in positions.values()))
            result.drawdown_curve.append(
                (peak_equity - total_equity) / peak_equity if peak_equity > 0 else 0
            )
            result.vol_multipliers.append(vol_mult)
            result.dd_multipliers.append(dd_mult)

            prev_close = current_price

        for sym, pos in list(positions.items()):
            exit_price = data["close"].iloc[-1]
            sell_cost = self._cost_calc.calc_sell_cost(exit_price, pos.quantity)
            commission = sell_cost.total_cost
            total_commission = pos.commission + commission
            if pos.side == PositionSide.LONG:
                pnl = (exit_price - pos.entry_price) * pos.quantity - total_commission
            else:
                pnl = (pos.entry_price - exit_price) * pos.quantity - total_commission
            risk = pos.risk_amount if pos.risk_amount > 0 else 1
            r_mult = pnl / risk
            holding_days = (
                pos.holding_days_at(result.dates[-1].to_pydatetime()) if result.dates else 0
            )

            trade = BacktestTrade(
                symbol=sym,
                side=pos.side,
                entry_date=pos.entry_time,
                exit_date=result.dates[-1] if result.dates else datetime.now(),
                entry_price=pos.entry_price,
                exit_price=exit_price,
                quantity=pos.quantity,
                pnl=pnl,
                pnl_pct=pnl / pos.current_value if pos.current_value > 0 else 0,
                r_multiple=r_mult,
                exit_reason="end_of_data",
                strategy_name=pos.strategy_name,
                holding_days=holding_days,
            )
            result.trades.append(trade)
            equity += pnl

        if not result.equity_curve:
            result.equity_curve.append(equity)
            result.dates.append(data.index[-1] if len(data) > 0 else datetime.now())

        return result

    def _calc_pnl(self, pos: Position, exit_price: float) -> tuple[float, float]:
        sell_cost = self._cost_calc.calc_sell_cost(exit_price, pos.quantity)
        total_commission = pos.commission + sell_cost.total_cost
        if pos.side == PositionSide.LONG:
            pnl = (exit_price - pos.entry_price) * pos.quantity - total_commission
        else:
            pnl = (pos.entry_price - exit_price) * pos.quantity - total_commission
        risk = pos.risk_amount if pos.risk_amount > 0 else 1
        r_mult = pnl / risk if risk > 0 else 0
        return pnl, r_mult

    def walk_forward(
        self,
        data: pd.DataFrame,
        symbol: str = "",
        train_ratio: float = 0.6,
        test_windows: int = 3,
        overfitting_threshold: float = 2.0,
    ) -> list[dict]:
        total_len = len(data)
        train_len = int(total_len * train_ratio)
        test_len = total_len - train_len
        window_size = test_len // test_windows

        results = []
        for i in range(test_windows):
            test_start = train_len + i * window_size
            test_end = min(test_start + window_size, total_len)

            if test_end <= test_start:
                break

            train_data = data.iloc[:train_len]
            test_data = data.iloc[test_start:test_end]

            train_result = self.run(train_data, symbol)
            test_result = self.run(test_data, symbol)

            overfitting_ratio = (
                train_result.total_return_pct / test_result.total_return_pct
                if test_result.total_return_pct != 0
                else float("inf")
            )

            overfitting_risk = (
                "high" if abs(overfitting_ratio) > overfitting_threshold
                else "medium" if abs(overfitting_ratio) > 1.5
                else "low"
            )

            results.append(
                {
                    "window": i + 1,
                    "train_period": f"{data.index[0]} ~ {data.index[train_len - 1]}",
                    "test_period": f"{data.index[test_start]} ~ {data.index[test_end - 1]}",
                    "train_return": round(train_result.total_return_pct * 100, 2),
                    "test_return": round(test_result.total_return_pct * 100, 2),
                    "train_sharpe": round(train_result.sharpe_ratio, 4),
                    "test_sharpe": round(test_result.sharpe_ratio, 4),
                    "train_max_dd": round(train_result.max_drawdown * 100, 2),
                    "test_max_dd": round(test_result.max_drawdown * 100, 2),
                    "train_trades": train_result.total_trades,
                    "test_trades": test_result.total_trades,
                    "overfitting_ratio": round(overfitting_ratio, 2),
                    "overfitting_risk": overfitting_risk,
                    "train_ashare": train_result.ashare_summary,
                    "test_ashare": test_result.ashare_summary,
                }
            )

        return results
