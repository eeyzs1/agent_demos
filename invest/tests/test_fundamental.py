from datetime import datetime

import pytest

from trading_system.data.fundamental import FundamentalData


class TestFundamentalData:
    def test_creation(self):
        fd = FundamentalData(
            symbol="600519",
            pe_ttm=30.5,
            pb=10.2,
            roe=25.3,
            revenue_growth=15.0,
            net_profit_growth=12.0,
        )
        assert fd.symbol == "600519"
        assert fd.pe_ttm == 30.5
        assert fd.pb == 10.2
        assert fd.roe == 25.3

    def test_defaults(self):
        fd = FundamentalData(symbol="600519")
        assert fd.pe_ttm is None
        assert fd.pb is None
        assert fd.roe is None
        assert fd.revenue_growth is None
        assert fd.net_profit_growth is None
        assert fd.fetched_at is not None

    def test_to_dict(self):
        fd = FundamentalData(symbol="600519", pe_ttm=30.5, pb=10.2)
        d = fd.to_dict()
        assert d["symbol"] == "600519"
        assert d["pe_ttm"] == 30.5
        assert d["pb"] == 10.2
        assert "fetched_at" in d

    def test_from_dict(self):
        d = {
            "symbol": "600519",
            "pe_ttm": 30.5,
            "pb": 10.2,
            "roe": 25.3,
            "fetched_at": datetime(2024, 1, 15, 10, 0, 0).isoformat(),
        }
        fd = FundamentalData.from_dict(d)
        assert fd.symbol == "600519"
        assert fd.pe_ttm == 30.5
        assert fd.roe == 25.3

    def test_roundtrip(self):
        fd = FundamentalData(
            symbol="600519",
            pe_ttm=30.5,
            pb=10.2,
            roe=25.3,
            revenue_growth=15.0,
            net_profit_growth=12.0,
            gross_margin=90.0,
            net_margin=50.0,
        )
        d = fd.to_dict()
        fd2 = FundamentalData.from_dict(d)
        assert fd2.symbol == fd.symbol
        assert fd2.pe_ttm == fd.pe_ttm
        assert fd2.pb == fd.pb
        assert fd2.roe == fd.roe

    def test_from_dict_ignores_extra_keys(self):
        d = {
            "symbol": "600519",
            "pe_ttm": 30.5,
            "unknown_field": "should be ignored",
        }
        fd = FundamentalData.from_dict(d)
        assert fd.symbol == "600519"
        assert fd.pe_ttm == 30.5
        assert not hasattr(fd, "unknown_field") or "unknown_field" not in fd.__dataclass_fields__


class TestDataStoreFinancial:
    def test_fetch_financial_unsupported_source(self):
        from trading_system.data.store import DataStore
        store = DataStore(cache_dir="./tmp_test_cache", db_url="sqlite:///./tmp_test.db")
        with pytest.raises(ValueError, match="does not support fetch_financial"):
            store.fetch_financial("600519", source="yfinance")
