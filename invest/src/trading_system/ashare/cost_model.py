from dataclasses import dataclass


@dataclass
class TradeCost:
    commission: float
    stamp_tax: float
    transfer_fee: float
    total_cost: float


class AShareCostCalculator:
    def __init__(
        self,
        commission_rate: float = 0.00025,
        min_commission: float = 5.0,
        stamp_tax_rate: float = 0.0005,
        transfer_fee_rate: float = 0.00001,
    ):
        self._commission_rate = commission_rate
        self._min_commission = min_commission
        self._stamp_tax_rate = stamp_tax_rate
        self._transfer_fee_rate = transfer_fee_rate

    @property
    def commission_rate(self) -> float:
        return self._commission_rate

    @property
    def min_commission(self) -> float:
        return self._min_commission

    @property
    def stamp_tax_rate(self) -> float:
        return self._stamp_tax_rate

    @property
    def transfer_fee_rate(self) -> float:
        return self._transfer_fee_rate

    def calc_buy_cost(self, price: float, quantity: float) -> TradeCost:
        amount = price * quantity
        commission = max(amount * self._commission_rate, self._min_commission)
        stamp_tax = 0.0
        transfer_fee = amount * self._transfer_fee_rate
        total = commission + stamp_tax + transfer_fee
        return TradeCost(
            commission=round(commission, 2),
            stamp_tax=round(stamp_tax, 2),
            transfer_fee=round(transfer_fee, 2),
            total_cost=round(total, 2),
        )

    def calc_sell_cost(self, price: float, quantity: float) -> TradeCost:
        amount = price * quantity
        commission = max(amount * self._commission_rate, self._min_commission)
        stamp_tax = amount * self._stamp_tax_rate
        transfer_fee = amount * self._transfer_fee_rate
        total = commission + stamp_tax + transfer_fee
        return TradeCost(
            commission=round(commission, 2),
            stamp_tax=round(stamp_tax, 2),
            transfer_fee=round(transfer_fee, 2),
            total_cost=round(total, 2),
        )

    def calc_total_cost(self, entry_price: float, exit_price: float, quantity: float) -> TradeCost:
        buy = self.calc_buy_cost(entry_price, quantity)
        sell = self.calc_sell_cost(exit_price, quantity)
        return TradeCost(
            commission=round(buy.commission + sell.commission, 2),
            stamp_tax=round(buy.stamp_tax + sell.stamp_tax, 2),
            transfer_fee=round(buy.transfer_fee + sell.transfer_fee, 2),
            total_cost=round(buy.total_cost + sell.total_cost, 2),
        )
