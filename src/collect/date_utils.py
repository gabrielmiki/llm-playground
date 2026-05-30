"""Date utility functions for market data collection."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_weekday_adjustment(target_date: str) -> str:
    """Adjust a date backwards to the nearest Friday if it falls on a weekend.

    Args:
        target_date: Date string in YYYY-MM-DD format.

    Returns:
        Adjusted date string in YYYY-MM-DD format.
        Returns the original date unchanged if it is already a weekday.
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d")

    if dt.weekday() == 5:
        adjusted = dt - timedelta(days=1)
        logger.info(
            "Date %s is Saturday, adjusted to %s",
            target_date, adjusted.strftime("%Y-%m-%d"),
        )
    elif dt.weekday() == 6:
        adjusted = dt - timedelta(days=2)
        logger.info(
            "Date %s is Sunday, adjusted to %s",
            target_date, adjusted.strftime("%Y-%m-%d"),
        )
    else:
        adjusted = dt

    return adjusted.strftime("%Y-%m-%d")
