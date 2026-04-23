import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ValidationIssue(Enum):
    ABNORMAL_PRICE = "abnormal_price"
    MISSING_DATA = "missing_data"
    STALE_DATA = "stale_data"
    NEGATIVE_PRICE = "negative_price"
    ZERO_VOLUME = "zero_volume"


class ValidationSeverity(Enum):
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    is_valid: bool = True
    issues: list[dict] = field(default_factory=list)

    def add_issue(
        self,
        issue_type: ValidationIssue,
        severity: ValidationSeverity,
        message: str,
        field_name: str = "",
        value: Optional[float] = None,
    ) -> None:
        self.is_valid = False
        self.issues.append(
            {
                "type": issue_type.value,
                "severity": severity.value,
                "message": message,
                "field": field_name,
                "value": value,
                "timestamp": datetime.now().isoformat(),
            }
        )

    @property
    def has_critical(self) -> bool:
        return any(i["severity"] == "critical" for i in self.issues)

    @property
    def has_error(self) -> bool:
        return any(i["severity"] == "error" for i in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i["severity"] == "warning")


@dataclass
class ValidatorConfig:
    abnormal_price_deviation_pct: float = 0.30
    stale_data_max_seconds: int = 300
    allow_zero_volume: bool = False


class DataValidator:
    def __init__(self, config: Optional[ValidatorConfig] = None):
        self._config = config or ValidatorConfig()
        self._validation_log: list[ValidationResult] = []

    @property
    def validation_log(self) -> list[ValidationResult]:
        return list(self._validation_log)

    def validate_price(
        self, price: Optional[float], prev_close: Optional[float] = None, symbol: str = ""
    ) -> ValidationResult:
        result = ValidationResult()

        if price is None or (isinstance(price, float) and math.isnan(price)):
            result.add_issue(
                ValidationIssue.MISSING_DATA,
                ValidationSeverity.ERROR,
                f"Price is None/NaN for {symbol}",
                field_name="price",
                value=price,
            )
            return result

        if price < 0:
            result.add_issue(
                ValidationIssue.NEGATIVE_PRICE,
                ValidationSeverity.CRITICAL,
                f"Negative price {price} for {symbol}",
                field_name="price",
                value=price,
            )
            return result

        if price == 0:
            result.add_issue(
                ValidationIssue.MISSING_DATA,
                ValidationSeverity.ERROR,
                f"Zero price for {symbol}",
                field_name="price",
                value=0.0,
            )
            return result

        if prev_close is not None and prev_close > 0:
            deviation = abs(price - prev_close) / prev_close
            if deviation > self._config.abnormal_price_deviation_pct:
                result.add_issue(
                    ValidationIssue.ABNORMAL_PRICE,
                    ValidationSeverity.CRITICAL,
                    f"Abnormal price deviation {deviation:.2%} for {symbol} "
                    f"(price={price}, prev_close={prev_close})",
                    field_name="price",
                    value=price,
                )

        self._validation_log.append(result)
        return result

    def validate_ohlcv(self, data: dict, symbol: str = "") -> ValidationResult:
        result = ValidationResult()

        required_fields = ["open", "high", "low", "close", "volume"]
        for f in required_fields:
            val = data.get(f)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                result.add_issue(
                    ValidationIssue.MISSING_DATA,
                    ValidationSeverity.ERROR,
                    f"Missing {f} for {symbol}",
                    field_name=f,
                    value=val,
                )

        if result.has_error:
            return result

        close = data.get("close", 0)
        if close is not None and close < 0:
            result.add_issue(
                ValidationIssue.NEGATIVE_PRICE,
                ValidationSeverity.CRITICAL,
                f"Negative close price for {symbol}",
                field_name="close",
                value=close,
            )

        volume = data.get("volume", 0)
        if volume is not None and volume == 0 and not self._config.allow_zero_volume:
            result.add_issue(
                ValidationIssue.ZERO_VOLUME,
                ValidationSeverity.WARNING,
                f"Zero volume for {symbol}",
                field_name="volume",
                value=0,
            )

        high = data.get("high")
        low = data.get("low")
        if high is not None and low is not None and high < low:
            result.add_issue(
                ValidationIssue.ABNORMAL_PRICE,
                ValidationSeverity.ERROR,
                f"High < Low for {symbol}: high={high}, low={low}",
                field_name="high",
                value=high,
            )

        prev_close = data.get("prev_close")
        if prev_close is not None and prev_close > 0 and close is not None:
            deviation = abs(close - prev_close) / prev_close
            if deviation > self._config.abnormal_price_deviation_pct:
                result.add_issue(
                    ValidationIssue.ABNORMAL_PRICE,
                    ValidationSeverity.CRITICAL,
                    f"Abnormal price deviation {deviation:.2%} for {symbol}",
                    field_name="close",
                    value=close,
                )

        self._validation_log.append(result)
        return result

    def validate_realtime(self, data: dict, symbol: str = "") -> ValidationResult:
        result = ValidationResult()

        current_price = data.get("current_price")
        if current_price is None or (isinstance(current_price, float) and math.isnan(current_price)):
            result.add_issue(
                ValidationIssue.MISSING_DATA,
                ValidationSeverity.ERROR,
                f"Missing current_price for {symbol}",
                field_name="current_price",
                value=current_price,
            )
            return result

        prev_close = data.get("prev_close")
        if prev_close is not None and prev_close > 0:
            deviation = abs(current_price - prev_close) / prev_close
            if deviation > self._config.abnormal_price_deviation_pct:
                result.add_issue(
                    ValidationIssue.ABNORMAL_PRICE,
                    ValidationSeverity.CRITICAL,
                    f"Abnormal price deviation {deviation:.2%} for {symbol}",
                    field_name="current_price",
                    value=current_price,
                )

        data_time_str = data.get("timestamp") or data.get("time")
        if data_time_str:
            try:
                if isinstance(data_time_str, (int, float)):
                    data_time = datetime.fromtimestamp(data_time_str)
                else:
                    data_time = datetime.fromisoformat(str(data_time_str))
                age = (datetime.now() - data_time).total_seconds()
                if age > self._config.stale_data_max_seconds:
                    result.add_issue(
                        ValidationIssue.STALE_DATA,
                        ValidationSeverity.WARNING,
                        f"Stale data for {symbol}: {age:.0f}s old",
                        field_name="timestamp",
                        value=age,
                    )
            except (ValueError, TypeError, OSError):
                pass

        self._validation_log.append(result)
        return result

    def validate_dataframe(self, df: pd.DataFrame, symbol: str = "") -> ValidationResult:
        result = ValidationResult()

        if df.empty:
            result.add_issue(
                ValidationIssue.MISSING_DATA,
                ValidationSeverity.ERROR,
                f"Empty dataframe for {symbol}",
                field_name="dataframe",
            )
            return result

        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                result.add_issue(
                    ValidationIssue.MISSING_DATA,
                    ValidationSeverity.ERROR,
                    f"Missing column '{col}' for {symbol}",
                    field_name=col,
                )
                continue

            nan_count = df[col].isna().sum()
            if nan_count > 0:
                result.add_issue(
                    ValidationIssue.MISSING_DATA,
                    ValidationSeverity.WARNING,
                    f"Column '{col}' has {nan_count} NaN values for {symbol}",
                    field_name=col,
                    value=float(nan_count),
                )

        if "close" in df.columns and len(df) > 1:
            prev_close = df["close"].shift(1)
            deviation = (df["close"] - prev_close).abs() / prev_close.replace(0, float("nan"))
            abnormal = deviation[deviation > self._config.abnormal_price_deviation_pct]
            if len(abnormal) > 0:
                result.add_issue(
                    ValidationIssue.ABNORMAL_PRICE,
                    ValidationSeverity.WARNING,
                    f"{len(abnormal)} abnormal price deviations for {symbol}",
                    field_name="close",
                    value=float(len(abnormal)),
                )

        self._validation_log.append(result)
        return result

    def is_safe_for_trading(self, result: ValidationResult) -> bool:
        return not result.has_critical and not result.has_error
