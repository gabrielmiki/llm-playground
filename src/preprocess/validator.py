from __future__ import annotations

import logging
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from datetime import date, datetime

from src.collect.market_data import MarketData

logger = logging.getLogger(__name__)


@dataclass
class ValidationWarning:
    category: str
    field: str
    message: str
    value: str | None


@dataclass
class ValidationResult:
    is_valid: bool
    warnings: list[ValidationWarning]


class MarketDataValidator:
    def validate(self, data: MarketData) -> ValidationResult:
        warnings: list[ValidationWarning] = []

        if not (data.open > 0):
            warnings.append(
                ValidationWarning(
                    category="invalid_price",
                    field="open",
                    message=f"open must be > 0, got {data.open}",
                    value=str(data.open),
                )
            )

        if not (data.high > 0):
            warnings.append(
                ValidationWarning(
                    category="invalid_price",
                    field="high",
                    message=f"high must be > 0, got {data.high}",
                    value=str(data.high),
                )
            )

        if data.high >= 0 and data.open >= 0 and data.high < data.open:
            warnings.append(
                ValidationWarning(
                    category="invalid_price_range",
                    field="high",
                    message=f"high ({data.high}) must be >= open ({data.open})",
                    value=str(data.high),
                )
            )

        if data.high >= 0 and data.close >= 0 and data.high < data.close:
            warnings.append(
                ValidationWarning(
                    category="invalid_price_range",
                    field="high",
                    message=f"high ({data.high}) must be >= close ({data.close})",
                    value=str(data.high),
                )
            )

        if not (data.low > 0):
            warnings.append(
                ValidationWarning(
                    category="invalid_price",
                    field="low",
                    message=f"low must be > 0, got {data.low}",
                    value=str(data.low),
                )
            )

        if data.low >= 0 and data.open >= 0 and data.low > data.open:
            warnings.append(
                ValidationWarning(
                    category="invalid_price_range",
                    field="low",
                    message=f"low ({data.low}) must be <= open ({data.open})",
                    value=str(data.low),
                )
            )

        if data.low >= 0 and data.close >= 0 and data.low > data.close:
            warnings.append(
                ValidationWarning(
                    category="invalid_price_range",
                    field="low",
                    message=f"low ({data.low}) must be <= close ({data.close})",
                    value=str(data.low),
                )
            )

        if not (data.close > 0):
            warnings.append(
                ValidationWarning(
                    category="invalid_price",
                    field="close",
                    message=f"close must be > 0, got {data.close}",
                    value=str(data.close),
                )
            )

        if not isinstance(data.volume, int) or data.volume < 0:
            warnings.append(
                ValidationWarning(
                    category="invalid_volume",
                    field="volume",
                    message=f"volume must be >= 0 int, got {data.volume}",
                    value=str(data.volume),
                )
            )

        if data.adjusted_close is not None and data.adjusted_close <= 0:
            warnings.append(
                ValidationWarning(
                    category="invalid_adjusted_close",
                    field="adjusted_close",
                    message=f"adjusted_close must be > 0 or None, got {data.adjusted_close}",
                    value=str(data.adjusted_close),
                )
            )

        try:
            ts_date = datetime.fromisoformat(data.timestamp).date()
            if ts_date > date.today():
                warnings.append(
                    ValidationWarning(
                        category="future_timestamp",
                        field="timestamp",
                        message=f"timestamp is in the future: {data.timestamp}",
                        value=data.timestamp,
                    )
                )
        except (ValueError, TypeError):
            warnings.append(
                ValidationWarning(
                    category="invalid_date",
                    field="timestamp",
                    message=f"timestamp is not valid ISO8601: {data.timestamp}",
                    value=data.timestamp,
                )
            )

        return ValidationResult(is_valid=len(warnings) == 0, warnings=warnings)

    def validate_many(
        self, records: Iterable[MarketData]
    ) -> Generator[ValidationResult, None, None]:
        for record in records:
            yield self.validate(record)


class NewsValidator:
    def validate(self, article: dict) -> ValidationResult:
        warnings: list[ValidationWarning] = []

        title = article.get("title", "")
        if not title:
            warnings.append(
                ValidationWarning(
                    category="missing_field",
                    field="title",
                    message="title is empty",
                    value=None,
                )
            )
        elif len(title) < 5:
            warnings.append(
                ValidationWarning(
                    category="title_too_short",
                    field="title",
                    message=f"title length {len(title)} is less than 5",
                    value=title,
                )
            )

        source = article.get("source", "")
        if not source:
            warnings.append(
                ValidationWarning(
                    category="missing_field",
                    field="source",
                    message="source is empty",
                    value=None,
                )
            )

        url = article.get("url", "")
        if not url:
            warnings.append(
                ValidationWarning(
                    category="missing_field",
                    field="url",
                    message="url is empty",
                    value=None,
                )
            )
        elif not (url.startswith("http://") or url.startswith("https://")):
            warnings.append(
                ValidationWarning(
                    category="invalid_url",
                    field="url",
                    message=f"url must start with http/https: {url[:50]}",
                    value=url[:50],
                )
            )

        published_at = article.get("published_at", "")
        if not published_at:
            warnings.append(
                ValidationWarning(
                    category="missing_field",
                    field="published_at",
                    message="published_at is empty",
                    value=None,
                )
            )
        else:
            try:
                datetime.fromisoformat(published_at)
            except (ValueError, TypeError):
                warnings.append(
                    ValidationWarning(
                        category="invalid_date",
                        field="published_at",
                        message=f"published_at is not valid ISO8601: {published_at[:50]}",
                        value=published_at[:50],
                    )
                )

        summary = article.get("summary", "")
        if not summary:
            warnings.append(
                ValidationWarning(
                    category="missing_field",
                    field="summary",
                    message="summary is empty",
                    value=None,
                )
            )

        return ValidationResult(is_valid=len(warnings) == 0, warnings=warnings)

    def validate_many(
        self, articles: Iterable[dict]
    ) -> Generator[ValidationResult, None, None]:
        for article in articles:
            yield self.validate(article)
