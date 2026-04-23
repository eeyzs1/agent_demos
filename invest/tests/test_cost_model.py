from trading_system.ashare.cost_model import AShareCostCalculator


class TestAShareCostCalculator:
    def setup_method(self):
        self.calc = AShareCostCalculator()

    def test_buy_cost_commission(self):
        cost = self.calc.calc_buy_cost(100.0, 1000)
        assert cost.commission == 25.0

    def test_buy_cost_no_stamp_tax(self):
        cost = self.calc.calc_buy_cost(100.0, 1000)
        assert cost.stamp_tax == 0.0

    def test_buy_cost_transfer_fee(self):
        cost = self.calc.calc_buy_cost(100.0, 1000)
        expected_transfer = 100.0 * 1000 * 0.00001
        assert cost.transfer_fee == round(expected_transfer, 2)

    def test_sell_cost_commission(self):
        cost = self.calc.calc_sell_cost(100.0, 1000)
        assert cost.commission == 25.0

    def test_sell_cost_stamp_tax(self):
        cost = self.calc.calc_sell_cost(100.0, 1000)
        expected_tax = 100.0 * 1000 * 0.0005
        assert cost.stamp_tax == round(expected_tax, 2)

    def test_sell_cost_transfer_fee(self):
        cost = self.calc.calc_sell_cost(100.0, 1000)
        expected_transfer = 100.0 * 1000 * 0.00001
        assert cost.transfer_fee == round(expected_transfer, 2)

    def test_min_commission_applied(self):
        cost = self.calc.calc_buy_cost(10.0, 100)
        assert cost.commission == 5.0

    def test_large_trade_commission(self):
        cost = self.calc.calc_buy_cost(100.0, 10000)
        expected_commission = 100.0 * 10000 * 0.00025
        assert cost.commission == round(expected_commission, 2)

    def test_total_cost(self):
        total = self.calc.calc_total_cost(100.0, 110.0, 1000)
        buy = self.calc.calc_buy_cost(100.0, 1000)
        sell = self.calc.calc_sell_cost(110.0, 1000)
        assert total.total_cost == round(buy.total_cost + sell.total_cost, 2)
        assert total.stamp_tax == sell.stamp_tax

    def test_custom_rates(self):
        calc = AShareCostCalculator(
            commission_rate=0.0003,
            min_commission=3.0,
            stamp_tax_rate=0.001,
            transfer_fee_rate=0.00002,
        )
        cost = calc.calc_sell_cost(100.0, 1000)
        assert cost.commission == 30.0
        expected_tax = 100.0 * 1000 * 0.001
        assert cost.stamp_tax == round(expected_tax, 2)

    def test_sell_stamp_tax_rate(self):
        assert self.calc.stamp_tax_rate == 0.0005

    def test_buy_total_cost_positive(self):
        cost = self.calc.calc_buy_cost(50.0, 2000)
        assert cost.total_cost > 0

    def test_sell_total_cost_greater_than_buy(self):
        buy = self.calc.calc_buy_cost(100.0, 1000)
        sell = self.calc.calc_sell_cost(100.0, 1000)
        assert sell.total_cost > buy.total_cost


class TestPaperBrokerAShareCost:
    def test_ashare_cost_mode(self):
        from trading_system.execution.broker import Order, OrderSide, OrderType, PaperBroker

        broker = PaperBroker(initial_capital=100000.0, use_ashare_cost=True)
        order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            price=100.0,
        )
        filled = broker.submit_order(order)
        assert filled.is_filled
        assert filled.commission > 0

    def test_ashare_sell_has_higher_cost(self):
        from trading_system.execution.broker import Order, OrderSide, OrderType, PaperBroker

        broker = PaperBroker(initial_capital=100000.0, use_ashare_cost=True)
        buy_order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            price=100.0,
        )
        buy_filled = broker.submit_order(buy_order)
        buy_commission = buy_filled.commission

        sell_order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=1000,
            price=100.0,
        )
        sell_filled = broker.submit_order(sell_order)
        sell_commission = sell_filled.commission
        assert sell_commission > buy_commission
