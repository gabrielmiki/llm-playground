from __future__ import annotations

import logging
from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from datetime import datetime

from src.collect.market_data import MarketData
from src.preprocess.validator import ValidationWarning

def decode_fused_record(data: dict) -> FusedRecord:
    """Deserialize a FusedRecord from a JSON dict.

    Mirrors the format written by ``FusedRecordWriter._fused_record_to_dict()``.
    """
    md_data = data.get("market_data")
    market_data = None
    if md_data is not None:
        md_data["volume"] = int(md_data["volume"])
        market_data = MarketData(**md_data)

    warnings = [ValidationWarning(**w) for w in data.get("warnings", [])]

    return FusedRecord(
        ticker=data["ticker"],
        date=data["date"],
        market_data=market_data,
        news_articles=data.get("news_articles", []),
        warnings=warnings,
    )

logger = logging.getLogger(__name__)


@dataclass
class FusedRecord:
    ticker: str
    date: str
    market_data: MarketData | None
    news_articles: list[dict]
    warnings: list[ValidationWarning] = field(default_factory=list)


@dataclass
class FusionResult:
    records: list[FusedRecord]
    fusion_warnings: list[ValidationWarning]


class DataFusionEngine:
    def fuse(
        self,
        ticker: str,
        date: str,
        market_data: MarketData | None,
        news_articles: list[dict],
    ) -> FusedRecord:
        warnings: list[ValidationWarning] = []

        if market_data is None:
            warnings.append(
                ValidationWarning(
                    category="missing_market_data",
                    field="market_data",
                    message=f"No market data available for {ticker} on {date}",
                    value=None,
                )
            )

        matching_articles: list[dict] = []
        for article in news_articles:
            article_date = _extract_date(article)
            if article_date == date:
                matching_articles.append(article)
            else:
                logger.debug(
                    f"Dropping article for {ticker}: date {article_date} != {date}"
                )

        return FusedRecord(
            ticker=ticker,
            date=date,
            market_data=market_data,
            news_articles=matching_articles,
            warnings=warnings,
        )

    def fuse_many(
        self,
        records: Iterable[tuple[str, str, MarketData | None, list[dict]]],
    ) -> Generator[FusedRecord, None, None]:
        for ticker, date, market_data, news_articles in records:
            yield self.fuse(ticker, date, market_data, news_articles)

    def fuse_all(
        self,
        records: list[tuple[str, str, MarketData | None, list[dict]]],
    ) -> FusionResult:
        fused_records = list(self.fuse_many(records))
        all_warnings: list[ValidationWarning] = []
        for r in fused_records:
            all_warnings.extend(r.warnings)
        return FusionResult(records=fused_records, fusion_warnings=all_warnings)


def _extract_date(article: object) -> str:
    if not isinstance(article, dict):
        return ""
    published_at = article.get("published_at", "")
    try:
        dt = datetime.fromisoformat(published_at)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""
