from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from trading_system.data.validator import (
    DataValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    ValidatorConfig,
)


@pytest.fixture
def validator():
    return DataValidator()


@pytest.fixture
def strict_validator():
    return DataValidator(ValidatorConfig(abnormal_price_deviation_pct=0.20))


class TestValidatePrice:
    def test_valid_price(self, validator):
        result = validator.validate_price(10.0, prev_close=9.8, symbol="TEST")
        assert result.is_valid

    def test_none_price(self, validator):
        result = validator.validate_price(None, symbol="TEST")
        assert not result.is_valid
        assert any(i["type"] == "missing_data" for i in result.issues)

    def test_nan_price(self, validator):
        result = validator.validate_price(float("nan"), symbol="TEST")
        assert not result.is_valid

    def test_negative_price(self, validator):
        result = validator.validate_price(-5.0, symbol="TEST")
        assert not result.is_valid
        assert result.has_critical

    def test_zero_price(self, validator):
        result = validator.validate_price(0.0, symbol="TEST")
        assert not result.is_valid

    def test_abnormal_price_deviation(self, validator):
        result = validator.validate_price(15.0, prev_close=10.0, symbol="TEST")
        assert not result.is_valid
        assert result.has_critical
        assert any(i["type"] == "abnormal_price" for i in result.issues)

    def test_normal_price_deviation(self, validator):
        result = validator.validate_price(10.5, prev_close=10.0, symbol="TEST")
        assert result.is_valid

    def test_strict_validator(self, strict_validator):
        result = strict_validator.validate_price(13.0, prev_close=10.0, symbol="TEST")
        assert not result.is_valid


class TestValidateOHLCV:
    def test_valid_ohlcv(self, validator):
        data = {
            "open": 10.0, "high": 10.5, "low": 9.8,
            "close": 10.2, "volume": 100000,
        }
        result = validator.validate_ohlcv(data, symbol="TEST")
        assert result.is_valid

    def test_missing_field(self, validator):
        data = {"open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2}
        result = validator.validate_ohlcv(data, symbol="TEST")
        assert not result.is_valid
        assert any(i["type"] == "missing_data" for i in result.issues)

    def test_nan_field(self, validator):
        data = {
            "open": 10.0, "high": 10.5, "low": 9.8,
            "close": float("nan"), "volume": 100000,
        }
        result = validator.validate_ohlcv(data, symbol="TEST")
        assert not result.is_valid

    def test_high_less_than_low(self, validator):
        data = {
            "open": 10.0, "high": 9.5, "low": 10.5,
            "close": 10.2, "volume": 100000,
        }
        result = validator.validate_ohlcv(data, symbol="TEST")
        assert not result.is_valid
        assert any(i["type"] == "abnormal_price" for i in result.issues)

    def test_zero_volume_warning(self, validator):
        data = {
            "open": 10.0, "high": 10.5, "low": 9.8,
            "close": 10.2, "volume": 0,
        }
        result = validator.validate_ohlcv(data, symbol="TEST")
        assert result.warning_count > 0

    def test_abnormal_close_with_prev_close(self, validator):
        data = {
            "open": 10.0, "high": 15.5, "low": 9.8,
            "close": 15.0, "volume": 100000, "prev_close": 10.0,
        }
        result = validator.validate_ohlcv(data, symbol="TEST")
        assert not result.is_valid


class TestValidateRealtime:
    def test_valid_realtime(self, validator):
        data = {
            "current_price": 10.5,
            "prev_close": 10.0,
            "timestamp": datetime.now().isoformat(),
        }
        result = validator.validate_realtime(data, symbol="TEST")
        assert result.is_valid

    def test_missing_current_price(self, validator):
        data = {"prev_close": 10.0}
        result = validator.validate_realtime(data, symbol="TEST")
        assert not result.is_valid

    def test_nan_current_price(self, validator):
        data = {"current_price": float("nan"), "prev_close": 10.0}
        result = validator.validate_realtime(data, symbol="TEST")
        assert not result.is_valid

    def test_abnormal_price(self, validator):
        data = {"current_price": 15.0, "prev_close": 10.0}
        result = validator.validate_realtime(data, symbol="TEST")
        assert not result.is_valid
        assert result.has_critical

    def test_stale_data(self, validator):
        old_time = (datetime.now() - timedelta(minutes=10)).isoformat()
        data = {"current_price": 10.5, "prev_close": 10.0, "timestamp": old_time}
        result = validator.validate_realtime(data, symbol="TEST")
        assert result.warning_count > 0

    def test_fresh_data_no_warning(self, validator):
        data = {
            "current_price": 10.5,
            "prev_close": 10.0,
            "timestamp": datetime.now().isoformat(),
        }
        result = validator.validate_realtime(data, symbol="TEST")
        stale_issues = [i for i in result.issues if i["type"] == "stale_data"]
        assert len(stale_issues) == 0


class TestValidateDataFrame:
    def test_valid_dataframe(self, validator):
        df = pd.DataFrame({
            "open": [10.0, 10.5], "high": [10.5, 11.0],
            "low": [9.8, 10.2], "close": [10.2, 10.8],
            "volume": [100000, 120000],
        })
        result = validator.validate_dataframe(df, symbol="TEST")
        assert result.is_valid

    def test_empty_dataframe(self, validator):
        df = pd.DataFrame()
        result = validator.validate_dataframe(df, symbol="TEST")
        assert not result.is_valid

    def test_missing_column(self, validator):
        df = pd.DataFrame({"open": [10.0], "close": [10.2]})
        result = validator.validate_dataframe(df, symbol="TEST")
        assert not result.is_valid

    def test_nan_values(self, validator):
        df = pd.DataFrame({
            "open": [10.0, np.nan], "high": [10.5, 11.0],
            "low": [9.8, 10.2], "close": [10.2, 10.8],
            "volume": [100000, 120000],
        })
        result = validator.validate_dataframe(df, symbol="TEST")
        assert result.warning_count > 0


class TestIsSafeForTrading:
    def test_safe_result(self, validator):
        result = ValidationResult(is_valid=True)
        assert validator.is_safe_for_trading(result)

    def test_unsafe_with_error(self, validator):
        result = ValidationResult(is_valid=False)
        result.add_issue(ValidationIssue.MISSING_DATA, ValidationSeverity.ERROR, "test")
        assert not validator.is_safe_for_trading(result)

    def test_unsafe_with_critical(self, validator):
        result = ValidationResult(is_valid=False)
        result.add_issue(ValidationIssue.ABNORMAL_PRICE, ValidationSeverity.CRITICAL, "test")
        assert not validator.is_safe_for_trading(result)

    def test_warning_still_safe(self, validator):
        result = ValidationResult(is_valid=False)
        result.add_issue(ValidationIssue.ZERO_VOLUME, ValidationSeverity.WARNING, "test")
        assert validator.is_safe_for_trading(result)


class TestValidationResult:
    def test_add_issue(self):
        result = ValidationResult()
        result.add_issue(ValidationIssue.MISSING_DATA, ValidationSeverity.ERROR, "test issue")
        assert not result.is_valid
        assert len(result.issues) == 1

    def test_has_critical(self):
        result = ValidationResult()
        result.add_issue(ValidationIssue.ABNORMAL_PRICE, ValidationSeverity.CRITICAL, "test")
        assert result.has_critical

    def test_has_error(self):
        result = ValidationResult()
        result.add_issue(ValidationIssue.MISSING_DATA, ValidationSeverity.ERROR, "test")
        assert result.has_error

    def test_warning_count(self):
        result = ValidationResult()
        result.add_issue(ValidationIssue.ZERO_VOLUME, ValidationSeverity.WARNING, "test1")
        result.add_issue(ValidationIssue.STALE_DATA, ValidationSeverity.WARNING, "test2")
        assert result.warning_count == 2
