"""Data collection package for financial APIs."""

from src.collect.client import RetryableHTTPClient
from src.collect.exceptions import (
    MarketDataAPIError,
    MarketDataError,
    MarketDataParseError,
    MarketDataUnavailableError,
    NewsDataAPIError,
    NewsDataError,
    NewsDataParseError,
    NewsDataUnavailableError,
)
from src.collect.market_data import MarketData, MarketDataCollector, fetch_market_data
from src.collect.news_collector import NewsCollector, fetch_news
from src.collect.rate_limiter import RateLimitConfig, TokenBucketRateLimiter

__all__ = [
    "MarketData",
    "MarketDataCollector",
    "MarketDataError",
    "MarketDataAPIError",
    "MarketDataParseError",
    "MarketDataUnavailableError",
    "NewsCollector",
    "NewsDataError",
    "NewsDataAPIError",
    "NewsDataParseError",
    "NewsDataUnavailableError",
    "RetryableHTTPClient",
    "RateLimitConfig",
    "TokenBucketRateLimiter",
    "fetch_market_data",
    "fetch_news",
]
