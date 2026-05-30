"""Historical fallback coordinator for graceful degradation.

When primary data sources fail, attempts to substitute data from the most
recent available cached FusedRecord within a 5-trading-day lookback window.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from src.collect.date_utils import get_weekday_adjustment
from src.preprocess.fusion import FusedRecord, decode_fused_record
from src.preprocess.validator import ValidationWarning

logger = logging.getLogger(__name__)

MAX_LOOKBACK_DAYS = 5


def build_degradation_warning(
    field_type: str,
    fallback_record: FusedRecord | None,
    ticker: str,
    target_date: str,
) -> ValidationWarning:
    """Build the appropriate degradation warning for a failed data source.

    Args:
        field_type: ``"market"`` or ``"news"``.
        fallback_record: The historical record used, or ``None`` if fallback
            was unavailable.
        ticker: Stock ticker symbol.
        target_date: Target date in YYYY-MM-DD format.

    Returns:
        A ``ValidationWarning`` with category ``degraded_market`` /
        ``degraded_news`` on success, or ``fallback_failed`` on failure.
    """
    if field_type == "market":
        field_name = "market_data"
        if fallback_record is not None and fallback_record.market_data is not None:
            return ValidationWarning(
                "degraded_market", field_name,
                f"Market data unavailable for {ticker} on {target_date}; "
                f"used fallback from {fallback_record.date}",
                value=None,
            )
        return ValidationWarning(
            "fallback_failed", field_name,
            f"Market data unavailable for {ticker} on {target_date} "
            "and no historical fallback found",
            value=None,
        )

    if field_type == "news":
        field_name = "news_articles"
        if fallback_record is not None and fallback_record.news_articles:
            return ValidationWarning(
                "degraded_news", field_name,
                f"News data unavailable for {ticker} on {target_date}; "
                f"used fallback from {fallback_record.date}",
                value=None,
            )
        return ValidationWarning(
            "fallback_failed", field_name,
            f"News data unavailable for {ticker} on {target_date} "
            "and no historical fallback found",
            value=None,
        )

    return ValidationWarning(
        "fallback_failed", "unknown",
        f"Unknown field_type {field_type!r}", value=None,
    )


def build_insufficient_data_warning(ticker: str, target_date: str) -> ValidationWarning:
    """Build a warning when both market and news are unavailable."""
    return ValidationWarning(
        "insufficient_data", "combined",
        f"No market data nor news available for {ticker} on {target_date}",
        value=None,
    )


def _load_fused_file(ticker: str, date_str: str, fused_dir: str) -> FusedRecord | None:
    """Load a FusedRecord from a single JSON file.

    Returns None if the file does not exist, is not valid JSON, or is
    missing required fields.
    """
    file_path = os.path.join(fused_dir, f"{ticker}_{date_str}.json")
    try:
        with open(file_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.debug("Cannot load %s: %s", file_path, exc)
        return None

    try:
        return decode_fused_record(data)
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("Cannot parse %s: %s", file_path, exc)
        return None


def _field_is_valid(record: FusedRecord, field_type: str) -> bool:
    """Check whether the requested field has usable data."""
    if field_type == "market":
        return record.market_data is not None
    if field_type == "news":
        return bool(record.news_articles)
    return False


def find_historical_fallback(
    ticker: str,
    target_date: str,
    field_type: str,
    fused_dir: str = "data/processed/fused",
) -> FusedRecord | None:
    """Look back up to 5 trading days for a cached FusedRecord with valid data.

    Scans ``fused_dir`` for files named ``{ticker}_{YYYY-MM-DD}.json``,
    applying weekend-only adjustment (Saturday → Friday, Sunday → Friday)
    matching ``date_utils.get_weekday_adjustment()``.

    Args:
        ticker: Stock ticker symbol.
        target_date: Original target date in YYYY-MM-DD format.
        field_type: ``"market"`` to check ``market_data``, ``"news"`` to
            check ``news_articles``.
        fused_dir: Directory containing cached FusedRecord JSON files.

    Returns:
        The first valid FusedRecord found, or ``None`` if no suitable
        record exists within the lookback window.
    """
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid target_date: %s", target_date)
        return None

    checked: set[str] = set()

    for offset in range(1, MAX_LOOKBACK_DAYS + 1):
        candidate = (dt - timedelta(days=offset)).strftime("%Y-%m-%d")
        adjusted = get_weekday_adjustment(candidate)

        if adjusted in checked:
            continue
        checked.add(adjusted)

        record = _load_fused_file(ticker, adjusted, fused_dir)
        if record is None:
            continue

        if _field_is_valid(record, field_type):
            logger.info(
                "Fallback found for %s %s: using %s from %s",
                ticker, field_type, field_type, adjusted,
            )
            return record

        logger.debug(
            "Fallback candidate %s has no valid %s, skipping",
            adjusted, field_type,
        )

    logger.warning(
        "No historical fallback found for %s %s within %d days",
        ticker, field_type, MAX_LOOKBACK_DAYS,
    )
    return None
