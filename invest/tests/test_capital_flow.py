from datetime import datetime

import pytest

from trading_system.data.capital_flow import NorthFlowData


class TestNorthFlowData:
    def test_creation(self):
        nf = NorthFlowData(
            date="2024-01-15",
            sh_net_inflow=50.0,
            sz_net_inflow=30.0,
            total_net_inflow=80.0,
        )
        assert nf.date == "2024-01-15"
        assert nf.sh_net_inflow == 50.0
        assert nf.sz_net_inflow == 30.0
        assert nf.total_net_inflow == 80.0

    def test_defaults(self):
        nf = NorthFlowData(date="2024-01-15")
        assert nf.sh_net_inflow is None
        assert nf.sz_net_inflow is None
        assert nf.total_net_inflow is None
        assert nf.fetched_at is not None

    def test_to_dict(self):
        nf = NorthFlowData(date="2024-01-15", sh_net_inflow=50.0, total_net_inflow=80.0)
        d = nf.to_dict()
        assert d["date"] == "2024-01-15"
        assert d["sh_net_inflow"] == 50.0
        assert d["total_net_inflow"] == 80.0

    def test_from_dict(self):
        d = {
            "date": "2024-01-15",
            "sh_net_inflow": 50.0,
            "total_net_inflow": 80.0,
            "fetched_at": datetime(2024, 1, 15, 10, 0, 0).isoformat(),
        }
        nf = NorthFlowData.from_dict(d)
        assert nf.date == "2024-01-15"
        assert nf.sh_net_inflow == 50.0

    def test_roundtrip(self):
        nf = NorthFlowData(
            date="2024-01-15",
            sh_net_inflow=50.0,
            sz_net_inflow=30.0,
            total_net_inflow=80.0,
            sh_balance=5000.0,
            sz_balance=3000.0,
        )
        d = nf.to_dict()
        nf2 = NorthFlowData.from_dict(d)
        assert nf2.date == nf.date
        assert nf2.total_net_inflow == nf.total_net_inflow


class TestDataStoreNorthFlow:
    def test_fetch_north_flow_unsupported_source(self):
        from trading_system.data.store import DataStore
        store = DataStore(cache_dir="./tmp_test_cache", db_url="sqlite:///./tmp_test.db")
        with pytest.raises(ValueError, match="does not support fetch_north_flow"):
            store.fetch_north_flow(source="yfinance")

    def test_fetch_dragon_tiger_unsupported_source(self):
        from trading_system.data.store import DataStore
        store = DataStore(cache_dir="./tmp_test_cache", db_url="sqlite:///./tmp_test.db")
        with pytest.raises(ValueError, match="does not support fetch_dragon_tiger"):
            store.fetch_dragon_tiger(date="20240115", source="yfinance")
