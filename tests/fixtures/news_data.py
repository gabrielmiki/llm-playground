"""Mock API responses for news data providers."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone


@pytest.fixture
def finnhub_response_valid() -> list[dict]:
    """Valid Finnhub company-news response."""
    return [
        {
            "category": "general",
            "datetime": 1705276800,
            "headline": "Apple Reports Record Q4 Earnings",
            "id": 123456789,
            "image": "https://example.com/image.jpg",
            "related": "AAPL",
            "source": "Reuters",
            "summary": "Apple Inc. announced record quarterly earnings with strong iPhone sales.",
            "url": "https://example.com/article",
        },
        {
            "category": "technology",
            "datetime": 1705190400,
            "headline": "Apple Unveils New AI Features",
            "id": 123456790,
            "image": "https://example.com/image2.jpg",
            "related": "AAPL",
            "source": "Bloomberg",
            "summary": "Apple announces new AI-powered features coming to iPhone.",
            "url": "https://example.com/article2",
        },
    ]


@pytest.fixture
def finnhub_response_empty() -> list[dict]:
    """Empty Finnhub response."""
    return []


@pytest.fixture
def finnhub_response_with_old_articles() -> list[dict]:
    """Finnhub response with some articles older than 365 days."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    old_ts = now_ts - (400 * 24 * 60 * 60)
    return [
        {
            "category": "general",
            "datetime": now_ts,
            "headline": "Recent Apple News",
            "id": 123456789,
            "source": "Reuters",
            "summary": "Recent news article from this year.",
            "url": "https://example.com/recent",
        },
        {
            "category": "general",
            "datetime": old_ts,
            "headline": "Old Apple News",
            "id": 123456790,
            "source": "Reuters",
            "summary": "Old news article from more than a year ago.",
            "url": "https://example.com/old",
        },
    ]


@pytest.fixture
def finnhub_response_missing_headline() -> list[dict]:
    """Finnhub response missing required 'headline' field."""
    return [
        {
            "category": "general",
            "datetime": 1705276800,
            "id": 123456789,
            "source": "Reuters",
            "summary": "Article without headline.",
            "url": "https://example.com/article",
        }
    ]


@pytest.fixture
def finnhub_response_invalid_format() -> dict:
    """Invalid Finnhub response (not a list)."""
    return {"error": "Invalid request"}


@pytest.fixture
def newsapi_response_valid() -> dict:
    """Valid NewsAPI everything response."""
    return {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "author": "John Doe",
                "title": "Apple Reports Record Q4 Earnings",
                "description": "Apple Inc. announced record quarterly earnings with strong iPhone sales.",
                "url": "https://example.com/article",
                "urlToImage": "https://example.com/image.jpg",
                "publishedAt": "2024-01-15T10:30:00Z",
                "content": "Apple Inc. announced record quarterly earnings...",
            },
            {
                "source": {"id": "bloomberg", "name": "Bloomberg"},
                "author": "Jane Smith",
                "title": "Apple Unveils New AI Features",
                "description": "Apple announces new AI-powered features coming to iPhone.",
                "url": "https://example.com/article2",
                "urlToImage": "https://example.com/image2.jpg",
                "publishedAt": "2024-01-14T14:00:00Z",
                "content": "Apple announces new AI features...",
            },
        ],
    }


@pytest.fixture
def newsapi_response_empty() -> dict:
    """Empty NewsAPI response."""
    return {
        "status": "ok",
        "totalResults": 0,
        "articles": [],
    }


@pytest.fixture
def newsapi_response_error() -> dict:
    """NewsAPI error response."""
    return {
        "status": "error",
        "code": "apiKeyInvalid",
        "message": "Your API key is invalid.",
    }


@pytest.fixture
def newsapi_response_with_old_articles() -> dict:
    """NewsAPI response with some articles older than 365 days."""
    now = datetime.now(timezone.utc)
    old = now.replace(year=now.year - 2)

    return {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "title": "Recent Apple News",
                "description": "Recent news article.",
                "url": "https://example.com/recent",
                "publishedAt": now.isoformat(),
            },
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "title": "Old Apple News",
                "description": "Old news article.",
                "url": "https://example.com/old",
                "publishedAt": old.isoformat(),
            },
        ],
    }


@pytest.fixture
def newsapi_response_missing_title() -> dict:
    """NewsAPI response missing required 'title' field."""
    return {
        "status": "ok",
        "totalResults": 1,
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "description": "Article without title.",
                "url": "https://example.com/article",
                "publishedAt": "2024-01-15T10:30:00Z",
            }
        ],
    }


@pytest.fixture
def normalized_article() -> dict:
    """Expected normalized news article."""
    return {
        "title": "Apple Reports Record Q4 Earnings",
        "source": "Reuters",
        "published_at": "2024-01-15T10:30:00+00:00",
        "url": "https://example.com/article",
        "summary": "Apple Inc. announced record quarterly earnings with strong iPhone sales.",
    }
