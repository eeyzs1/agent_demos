from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class NorthFlowData:
    date: str
    sh_net_inflow: Optional[float] = None
    sz_net_inflow: Optional[float] = None
    total_net_inflow: Optional[float] = None
    sh_balance: Optional[float] = None
    sz_balance: Optional[float] = None
    total_balance: Optional[float] = None
    fetched_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "sh_net_inflow": self.sh_net_inflow,
            "sz_net_inflow": self.sz_net_inflow,
            "total_net_inflow": self.total_net_inflow,
            "sh_balance": self.sh_balance,
            "sz_balance": self.sz_balance,
            "total_balance": self.total_balance,
            "fetched_at": self.fetched_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NorthFlowData":
        d = dict(data)
        if "fetched_at" in d and isinstance(d["fetched_at"], str):
            d["fetched_at"] = datetime.fromisoformat(d["fetched_at"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
