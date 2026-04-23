import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    r_multiple = Column(Float, nullable=True)
    exit_reason = Column(String(30), nullable=True)
    strategy_name = Column(String(50), nullable=True)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    holding_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    trailing_stop = Column(Float, nullable=True)
    highest_price = Column(Float, nullable=True)
    strategy_name = Column(String(50), nullable=True)
    snapshot_time = Column(DateTime, default=datetime.now)


class TradeDatabase:
    def __init__(self, db_url: str = "sqlite:///./data/trading.db"):
        self._engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

    def save_trade(self, trade: dict) -> None:
        with Session(self._engine) as session:
            record = TradeRecord(
                symbol=trade.get("symbol", ""),
                side=str(trade.get("side", "")),
                quantity=trade.get("quantity", 0),
                entry_price=trade.get("entry_price", 0),
                exit_price=trade.get("exit_price"),
                stop_loss=trade.get("stop_loss"),
                take_profit=trade.get("take_profit"),
                pnl=trade.get("pnl"),
                pnl_pct=trade.get("pnl_pct"),
                r_multiple=trade.get("r_multiple"),
                exit_reason=trade.get("reason", ""),
                strategy_name=trade.get("strategy", ""),
                entry_time=pd.Timestamp(trade.get("entry_time", datetime.now())).to_pydatetime()
                if trade.get("entry_time")
                else datetime.now(),
                exit_time=pd.Timestamp(trade.get("exit_time")).to_pydatetime()
                if trade.get("exit_time")
                else None,
                holding_days=trade.get("holding_days"),
            )
            session.add(record)
            session.commit()

    def save_position_snapshot(self, positions: list[dict]) -> None:
        with Session(self._engine) as session:
            for pos in positions:
                snapshot = PositionSnapshot(
                    symbol=pos.get("symbol", ""),
                    side=str(pos.get("side", "")),
                    quantity=pos.get("quantity", 0),
                    entry_price=pos.get("entry_price", 0),
                    stop_loss=pos.get("stop_loss"),
                    take_profit=pos.get("take_profit"),
                    trailing_stop=pos.get("trailing_stop"),
                    highest_price=pos.get("highest_price"),
                    strategy_name=pos.get("strategy_name", ""),
                )
                session.add(snapshot)
            session.commit()

    def query_trades(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        with Session(self._engine) as session:
            query = session.query(TradeRecord)
            if symbol:
                query = query.filter(TradeRecord.symbol == symbol)
            if strategy:
                query = query.filter(TradeRecord.strategy_name == strategy)
            if start_date:
                query = query.filter(TradeRecord.entry_time >= start_date)
            if end_date:
                query = query.filter(TradeRecord.entry_time <= end_date)

            records = query.all()
            if not records:
                return pd.DataFrame()

            data = [
                {
                    "symbol": r.symbol,
                    "side": r.side,
                    "quantity": r.quantity,
                    "entry_price": r.entry_price,
                    "exit_price": r.exit_price,
                    "pnl": r.pnl,
                    "pnl_pct": r.pnl_pct,
                    "r_multiple": r.r_multiple,
                    "exit_reason": r.exit_reason,
                    "strategy": r.strategy_name,
                    "entry_time": r.entry_time,
                    "exit_time": r.exit_time,
                    "holding_days": r.holding_days,
                }
                for r in records
            ]
            return pd.DataFrame(data)

    def get_performance_summary(self) -> dict:
        with Session(self._engine) as session:
            total = session.query(TradeRecord).count()
            if total == 0:
                return {"total_trades": 0}

            from sqlalchemy import func

            wins = session.query(TradeRecord).filter(TradeRecord.pnl > 0).count()
            total_pnl = session.query(func.sum(TradeRecord.pnl)).scalar() or 0
            avg_r = session.query(func.avg(TradeRecord.r_multiple)).scalar() or 0

            return {
                "total_trades": total,
                "win_rate": round(wins / total, 4) if total > 0 else 0,
                "total_pnl": round(total_pnl, 2),
                "avg_r_multiple": round(avg_r, 4),
            }
