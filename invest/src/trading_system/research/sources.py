from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class NewsItem:
    title: str
    source: str
    url: str = ""
    publish_time: Optional[datetime] = None
    content: str = ""
    symbols: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    relevance_score: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class ResearchReport:
    title: str
    source: str
    author: str = ""
    publish_time: Optional[datetime] = None
    rating: str = ""
    target_price: float = 0.0
    content: str = ""
    symbols: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)


@dataclass
class Announcement:
    title: str
    symbol: str
    announce_time: Optional[datetime] = None
    content: str = ""
    ann_type: str = ""
    importance: str = "normal"


class DataSourceBase(ABC):
    @abstractmethod
    def fetch_news(self, keyword: str = "", limit: int = 20) -> list[NewsItem]:
        pass

    @abstractmethod
    def fetch_reports(self, symbol: str = "", limit: int = 10) -> list[ResearchReport]:
        pass

    @abstractmethod
    def fetch_announcements(self, symbol: str, limit: int = 10) -> list[Announcement]:
        pass

    @abstractmethod
    def name(self) -> str:
        pass


class AKShareNewsSource(DataSourceBase):
    def fetch_news(self, keyword: str = "", limit: int = 20) -> list[NewsItem]:
        try:
            import akshare as ak

            df = ak.stock_news_em(symbol=keyword) if keyword else ak.stock_news_em(symbol="")

            items = []
            for _, row in df.head(limit).iterrows():
                items.append(
                    NewsItem(
                        title=str(row.get("新闻标题", "")),
                        source=str(row.get("新闻来源", "")),
                        content=str(row.get("新闻内容", "")),
                        publish_time=pd.to_datetime(row.get("发布时间", None), errors="coerce"),
                        url=str(row.get("新闻链接", "")),
                    )
                )
            return items
        except Exception:
            return []

    def fetch_reports(self, symbol: str = "", limit: int = 10) -> list[ResearchReport]:
        try:
            import akshare as ak

            df = ak.stock_analyst_detail_em(analyst_id=symbol) if symbol else pd.DataFrame()

            reports = []
            for _, row in df.head(limit).iterrows():
                reports.append(
                    ResearchReport(
                        title=str(row.get("报告标题", "")),
                        source=str(row.get("研究机构", "")),
                        author=str(row.get("分析师", "")),
                        rating=str(row.get("评级", "")),
                        publish_time=pd.to_datetime(row.get("日期", None), errors="coerce"),
                    )
                )
            return reports
        except Exception:
            return []

    def fetch_announcements(self, symbol: str, limit: int = 10) -> list[Announcement]:
        try:
            import akshare as ak

            df = ak.stock_notice_report(symbol=symbol)

            announcements = []
            for _, row in df.head(limit).iterrows():
                announcements.append(
                    Announcement(
                        title=str(row.get("公告标题", "")),
                        symbol=symbol,
                        announce_time=pd.to_datetime(row.get("公告日期", None), errors="coerce"),
                        ann_type=str(row.get("公告类型", "")),
                        content=str(row.get("公告内容", "")),
                    )
                )
            return announcements
        except Exception:
            return []

    def name(self) -> str:
        return "akshare"


class EastMoneySectorSource(DataSourceBase):
    def fetch_news(self, keyword: str = "", limit: int = 20) -> list[NewsItem]:
        try:
            import akshare as ak

            df = ak.stock_board_concept_name_em()

            items = []
            for _, row in df.head(limit).iterrows():
                items.append(
                    NewsItem(
                        title=str(row.get("板块名称", "")),
                        source="eastmoney_concept",
                        tags=["concept", "sector"],
                    )
                )
            return items
        except Exception:
            return []

    def fetch_reports(self, symbol: str = "", limit: int = 10) -> list[ResearchReport]:
        return []

    def fetch_announcements(self, symbol: str, limit: int = 10) -> list[Announcement]:
        return []

    def name(self) -> str:
        return "eastmoney_sector"


class ResearchDataAggregator:
    def __init__(self):
        self._sources: list[DataSourceBase] = [
            AKShareNewsSource(),
            EastMoneySectorSource(),
        ]

    def add_source(self, source: DataSourceBase) -> None:
        self._sources.append(source)

    def fetch_all_news(self, keyword: str = "", limit: int = 20) -> list[NewsItem]:
        all_items = []
        for source in self._sources:
            try:
                items = source.fetch_news(keyword=keyword, limit=limit)
                all_items.extend(items)
            except Exception:
                continue

        all_items.sort(key=lambda x: x.publish_time or datetime.min, reverse=True)
        return all_items[:limit]

    def fetch_all_reports(self, symbol: str = "", limit: int = 10) -> list[ResearchReport]:
        all_reports = []
        for source in self._sources:
            try:
                reports = source.fetch_reports(symbol=symbol, limit=limit)
                all_reports.extend(reports)
            except Exception:
                continue

        all_reports.sort(key=lambda x: x.publish_time or datetime.min, reverse=True)
        return all_reports[:limit]

    def fetch_all_announcements(self, symbol: str, limit: int = 10) -> list[Announcement]:
        all_anns = []
        for source in self._sources:
            try:
                anns = source.fetch_announcements(symbol=symbol, limit=limit)
                all_anns.extend(anns)
            except Exception:
                continue

        all_anns.sort(key=lambda x: x.announce_time or datetime.min, reverse=True)
        return all_anns[:limit]

    def fetch_sector_data(self) -> pd.DataFrame:
        try:
            import akshare as ak

            df = ak.stock_board_industry_name_em()
            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["name"] = df.get("板块名称", df.get("name", ""))
            result["change_pct"] = df.get("涨跌幅", df.get("change_pct", 0))
            result["volume"] = df.get("总成交量", df.get("volume", 0))
            result["amount"] = df.get("总成交额", df.get("amount", 0))
            result["close"] = df.get("最新价", df.get("close", 0))

            if "领涨股票" in df.columns:
                result["symbols"] = df["领涨股票"]

            return result
        except Exception:
            return pd.DataFrame()

    def fetch_concept_sectors(self) -> pd.DataFrame:
        try:
            import akshare as ak

            df = ak.stock_board_concept_name_em()
            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["name"] = df.get("板块名称", df.get("name", ""))
            result["change_pct"] = df.get("涨跌幅", df.get("change_pct", 0))
            result["volume"] = df.get("总成交量", df.get("volume", 0))
            result["amount"] = df.get("总成交额", df.get("amount", 0))
            result["close"] = df.get("最新价", df.get("close", 0))

            return result
        except Exception:
            return pd.DataFrame()

    def fetch_fund_flow(self) -> pd.DataFrame:
        try:
            import akshare as ak

            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["symbol"] = df.get("代码", df.get("symbol", ""))
            result["name"] = df.get("名称", df.get("name", ""))
            result["change_pct"] = df.get("涨跌幅", df.get("change_pct", 0))
            result["main_net_inflow"] = df.get("主力净流入-净额", df.get("main_net_inflow", 0))
            result["main_net_ratio"] = df.get("主力净流入-净占比", df.get("main_net_ratio", 0))

            return result
        except Exception:
            return pd.DataFrame()
