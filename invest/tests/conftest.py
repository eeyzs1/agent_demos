import pytest

from trading_system.core.config import AppConfig, RiskConfig


@pytest.fixture
def app_config():
    return AppConfig()


@pytest.fixture
def risk_config():
    return RiskConfig()


@pytest.fixture
def initial_capital():
    return 100000.0
