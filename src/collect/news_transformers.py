"""API-specific response transformers for news data normalization."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from src.collect.exceptions import NewsDataAPIError, NewsDataParseError

logger = logging.getLogger(__name__)

NewsArticle = dict[str, str]


def _unix_to_iso8601(timestamp: int | float) -> str:
    """Convert Unix timestamp to ISO8601 UTC string."""
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


def _validate_required_fields(
    data: dict[str, Any],
    required_fields: list[str],
    provider: str,
) -> None:
    """Validate that all required fields are present in the data."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        error_msg = f"Missing required field(s): {', '.join(missing)}"
        logger.error(f"[{provider}] {error_msg} | Response snippet: {str(data)[:200]}")
        raise NewsDataParseError(error_msg)


def transform_finnhub_news(
    response: list[dict[str, Any]],
    target_date: str,
    max_age_days: int = 365,
) -> list[NewsArticle]:
    """
    Transform Finnhub Company News API response to normalized schema.

    Finnhub company-news response structure:
    [
        {
            "category": "general",
            "datetime": 1704067200,
            "headline": "Apple Reports Record Q4 Earnings",
            "id": 123456789,
            "image": "https://example.com/image.jpg",
            "related": "AAPL",
            "source": "Reuters",
            "summary": "Apple Inc. announced record quarterly earnings...",
            "url": "https://example.com/article"
        }
    ]
    """
    if not isinstance(response, list):
        error_msg = f"Invalid Finnhub response: expected list, got {type(response)}"
        logger.error(f"{error_msg} | Response: {str(response)[:200]}")
        raise NewsDataParseError(error_msg)

    if not response:
        logger.info("[Finnhub] No news articles returned")
        return []

    articles: list[NewsArticle] = []
    target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    cutoff_dt = target_dt - timedelta(days=max_age_days)

    excluded_count = 0
    for item in response:
        if not isinstance(item, dict):
            continue

        published_at = item.get("datetime")
        if published_at is None:
            continue

        article_dt = datetime.fromtimestamp(published_at, tz=timezone.utc)

        if article_dt < cutoff_dt:
            excluded_count += 1
            continue

        article = {
            "title": item.get("headline", ""),
            "source": item.get("source", ""),
            "published_at": _unix_to_iso8601(published_at),
            "url": item.get("url", ""),
            "summary": item.get("summary", ""),
        }
        articles.append(article)

    if excluded_count > 0:
        logger.warning(
            f"[Finnhub] Excluded {excluded_count} article(s) older than {max_age_days} days"
        )

    return articles


def transform_newsapi(
    response: dict[str, Any],
    target_date: str,
    max_age_days: int = 365,
) -> list[NewsArticle]:
    """
    Transform NewsAPI Everything endpoint response to normalized schema.

    NewsAPI response structure:
    {
        "status": "ok",
        "totalResults": 1,
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "author": "John Doe",
                "title": "Apple Reports Record Q4 Earnings",
                "description": "Apple Inc. announced record quarterly earnings...",
                "url": "https://example.com/article",
                "urlToImage": "https://example.com/image.jpg",
                "publishedAt": "2024-01-15T10:30:00Z",
                "content": "Apple Inc. announced... (truncated to 200 chars)"
            }
        ]
    }

    Error response structure:
    {
        "status": "error",
        "code": "apiKeyInvalid",
        "message": "Your API key is invalid."
    }
    """
    status = response.get("status")
    if status == "error":
        code = response.get("code", "unknown")
        message = response.get("message", "Unknown error")
        error_msg = f"[{code}] {message}"
        logger.error(f"[NewsAPI] {error_msg}")
        raise NewsDataAPIError(error_msg)

    if status != "ok":
        error_msg = f"Unexpected NewsAPI status: {status}"
        logger.error(f"[NewsAPI] {error_msg} | Response: {str(response)[:200]}")
        raise NewsDataParseError(error_msg)

    articles_data = response.get("articles", [])
    if not articles_data:
        logger.info("[NewsAPI] No news articles returned")
        return []

    target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    cutoff_dt = target_dt - timedelta(days=max_age_days)

    articles: list[NewsArticle] = []
    excluded_count = 0

    for item in articles_data:
        if not isinstance(item, dict):
            continue

        published_at_str = item.get("publishedAt")
        if not published_at_str:
            continue

        try:
            if "Z" in published_at_str:
                article_dt = datetime.fromisoformat(
                    published_at_str.replace("Z", "+00:00")
                )
            else:
                article_dt = datetime.fromisoformat(published_at_str)
        except ValueError:
            logger.warning(f"[NewsAPI] Failed to parse date: {published_at_str}")
            continue

        if article_dt.replace(tzinfo=timezone.utc) < cutoff_dt:
            excluded_count += 1
            continue

        source_obj = item.get("source", {})
        source_name = (
            source_obj.get("name", "")
            if isinstance(source_obj, dict)
            else str(source_obj)
        )

        article = {
            "title": item.get("title", ""),
            "source": source_name,
            "published_at": article_dt.isoformat(),
            "url": item.get("url", ""),
            "summary": item.get("description", "") or item.get("content", ""),
        }
        articles.append(article)

    if excluded_count > 0:
        logger.warning(
            f"[NewsAPI] Excluded {excluded_count} article(s) older than {max_age_days} days"
        )

    return articles
