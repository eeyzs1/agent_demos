from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FundamentalData:
    symbol: str
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth: Optional[float] = None
    net_profit_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    eps: Optional[float] = None
    bps: Optional[float] = None
    report_date: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "pe_ttm": self.pe_ttm,
            "pb": self.pb,
            "roe": self.roe,
            "revenue_growth": self.revenue_growth,
            "net_profit_growth": self.net_profit_growth,
            "gross_margin": self.gross_margin,
            "net_margin": self.net_margin,
            "debt_ratio": self.debt_ratio,
            "current_ratio": self.current_ratio,
            "eps": self.eps,
            "bps": self.bps,
            "report_date": self.report_date,
            "fetched_at": self.fetched_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FundamentalData":
        d = dict(data)
        if "fetched_at" in d and isinstance(d["fetched_at"], str):
            d["fetched_at"] = datetime.fromisoformat(d["fetched_at"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
