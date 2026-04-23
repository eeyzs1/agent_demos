import pytest

from trading_system.ashare.calculator import (
    BoardType,
    calc_limit_price,
    clamp_price,
    detect_board_type,
    is_within_limit,
)
from trading_system.execution.broker import Order, OrderSide, OrderType, PaperBroker


class TestCalcLimitPrice:
    def test_main_board_upper(self):
        result = calc_limit_price(10.0, BoardType.MAIN)
        assert result.upper_limit == 11.0
        assert result.lower_limit == 9.0
        assert result.board_type == BoardType.MAIN

    def test_main_board_lower(self):
        result = calc_limit_price(10.0, BoardType.MAIN)
        assert result.lower_limit == 9.0

    def test_gem_board(self):
        result = calc_limit_price(10.0, BoardType.GEM)
        assert result.upper_limit == 12.0
        assert result.lower_limit == 8.0

    def test_star_board(self):
        result = calc_limit_price(10.0, BoardType.STAR)
        assert result.upper_limit == 12.0
        assert result.lower_limit == 8.0

    def test_st_board(self):
        result = calc_limit_price(5.0, BoardType.ST)
        assert result.upper_limit == 5.25
        assert result.lower_limit == 4.75

    def test_bse_board(self):
        result = calc_limit_price(10.0, BoardType.BSE)
        assert result.upper_limit == 13.0
        assert result.lower_limit == 7.0

    def test_invalid_prev_close(self):
        with pytest.raises(ValueError):
            calc_limit_price(0, BoardType.MAIN)
        with pytest.raises(ValueError):
            calc_limit_price(-1, BoardType.MAIN)

    def test_rounding(self):
        result = calc_limit_price(13.33, BoardType.MAIN)
        assert result.upper_limit == 14.66
        assert result.lower_limit == 12.0


class TestClampPrice:
    def test_price_within_limit(self):
        assert clamp_price(10.5, 10.0, BoardType.MAIN) == 10.5

    def test_price_above_upper(self):
        assert clamp_price(12.0, 10.0, BoardType.MAIN) == 11.0

    def test_price_below_lower(self):
        assert clamp_price(7.0, 10.0, BoardType.MAIN) == 9.0

    def test_price_at_limits(self):
        assert clamp_price(11.0, 10.0, BoardType.MAIN) == 11.0
        assert clamp_price(9.0, 10.0, BoardType.MAIN) == 9.0


class TestIsWithinLimit:
    def test_within(self):
        assert is_within_limit(10.5, 10.0, BoardType.MAIN) is True

    def test_at_upper(self):
        assert is_within_limit(11.0, 10.0, BoardType.MAIN) is True

    def test_above_upper(self):
        assert is_within_limit(11.5, 10.0, BoardType.MAIN) is False

    def test_below_lower(self):
        assert is_within_limit(8.5, 10.0, BoardType.MAIN) is False


class TestDetectBoardType:
    def test_main_board_60x(self):
        assert detect_board_type("600519") == BoardType.MAIN

    def test_main_board_000(self):
        assert detect_board_type("000001") == BoardType.MAIN

    def test_main_board_001(self):
        assert detect_board_type("001234") == BoardType.MAIN

    def test_gem_board_300(self):
        assert detect_board_type("300750") == BoardType.GEM

    def test_gem_board_301(self):
        assert detect_board_type("301234") == BoardType.GEM

    def test_star_board_688(self):
        assert detect_board_type("688981") == BoardType.STAR

    def test_st_by_name(self):
        assert detect_board_type("600519", "ST某某") == BoardType.ST
        assert detect_board_type("600519", "*ST某某") == BoardType.ST

    def test_bse_board(self):
        assert detect_board_type("830799") == BoardType.BSE
        assert detect_board_type("430047") == BoardType.BSE

    def test_empty_symbol(self):
        assert detect_board_type("") == BoardType.MAIN


class TestPaperBrokerLimitCheck:
    def test_limit_check_clamps_price(self):
        broker = PaperBroker(initial_capital=100000.0, enable_limit_check=True)
        order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=12.0,
            metadata={"prev_close": 10.0},
        )
        filled = broker.submit_order(order)
        assert filled.is_filled
        assert filled.filled_price <= 11.0 * (1 + broker._slippage_pct) + 0.01

    def test_limit_check_disabled(self):
        broker = PaperBroker(initial_capital=100000.0, enable_limit_check=False)
        order = Order(
            order_id="",
            symbol="600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=12.0,
        )
        filled = broker.submit_order(order)
        assert filled.is_filled
