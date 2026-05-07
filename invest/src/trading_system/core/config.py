from pathlib import Path
import os

import yaml
from pydantic import BaseModel, Field


def _load_dotenv(dotenv_path: Path | None = None) -> None:
    if dotenv_path is None:
        dotenv_path = Path(".env")
    if not dotenv_path.exists():
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path)
        return
    except ImportError:
        pass

    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class RiskConfig(BaseModel):
    max_risk_per_trade: float = Field(default=0.02, ge=0.001, le=0.1)
    max_drawdown_limit: float = Field(default=0.20, ge=0.05, le=0.5)
    max_consecutive_losses: int = Field(default=10, ge=3)
    circuit_breaker_loss_pct: float = Field(default=0.05, ge=0.01, le=0.2)
    circuit_breaker_cooldown_days: int = Field(default=3, ge=1)
    target_volatility: float = Field(default=0.20, ge=0.05, le=0.5)
    vol_lookback_days: int = Field(default=20, ge=5, le=60)
    drawdown_soft_limit: float = Field(default=0.10, ge=0.02, le=0.20)
    drawdown_hard_limit: float = Field(default=0.20, ge=0.05, le=0.50)
    trailing_stop_pct: float = Field(default=0.05, ge=0.01, le=0.15)
    trailing_stop_activate_pct: float = Field(default=0.03, ge=0.01, le=0.10)
    max_holding_days: int = Field(default=30, ge=1, le=365)
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)


class StrategyConfig(BaseModel):
    default_stop_loss_pct: float = Field(default=0.05, ge=0.01, le=0.2)
    default_take_profit_rr: float = Field(default=3.0, ge=1.0)
    min_rr_ratio: float = Field(default=1.5, ge=1.0)


class DataConfig(BaseModel):
    primary_source: str = "akshare"
    cache_dir: str = "./data/cache"
    database_url: str = "sqlite:///./data/trading.db"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    audit_file: str = "./logs/audit.jsonl"
    trade_log: str = "./logs/trades.jsonl"


class TradingConfig(BaseModel):
    mode: str = Field(default="paper")
    initial_capital: float = Field(default=100000.0, gt=0)
    base_currency: str = "CNY"
    qmt_path: str = Field(default_factory=lambda: _env("QMT_PATH"))
    qmt_account: str = Field(default_factory=lambda: _env("QMT_ACCOUNT"))
    qmt_password: str = Field(default_factory=lambda: _env("QMT_PASSWORD"))
    qmt_trade_mode: int = Field(default=0)


class NotificationConfig(BaseModel):
    feishu_webhook: str = Field(default_factory=lambda: _env("FEISHU_WEBHOOK"))
    dingtalk_webhook: str = Field(default_factory=lambda: _env("DINGTALK_WEBHOOK"))
    dingtalk_secret: str = Field(default_factory=lambda: _env("DINGTALK_SECRET"))
    wechat_sckey: str = Field(default_factory=lambda: _env("WECHAT_SCKEY"))


class AppConfig(BaseModel):
    trading: TradingConfig = TradingConfig()
    risk: RiskConfig = RiskConfig()
    strategy: StrategyConfig = StrategyConfig()
    data: DataConfig = DataConfig()
    logging: LoggingConfig = LoggingConfig()
    notification: NotificationConfig = NotificationConfig()

    @classmethod
    def from_yaml(cls, path: str | Path, load_env: bool = True) -> "AppConfig":
        if load_env:
            _load_dotenv(Path(".env"))

        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        for section in ("trading", "notification"):
            if section not in raw:
                raw[section] = {}
        raw["trading"]["qmt_path"] = _env("QMT_PATH")
        raw["trading"]["qmt_account"] = _env("QMT_ACCOUNT")
        raw["trading"]["qmt_password"] = _env("QMT_PASSWORD")
        raw["notification"]["feishu_webhook"] = _env("FEISHU_WEBHOOK")
        raw["notification"]["dingtalk_webhook"] = _env("DINGTALK_WEBHOOK")
        raw["notification"]["dingtalk_secret"] = _env("DINGTALK_SECRET")
        raw["notification"]["wechat_sckey"] = _env("WECHAT_SCKEY")

        return cls(**raw)

    @classmethod
    def save_default(cls, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        config = cls()
        raw = config.model_dump()
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)
