"""HTTP client fixture with retry logic for testing."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from tests.fixtures.rate_limiter import TokenBucketRateLimiter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    jitter: float = 0.5
    retryable_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)


@dataclass
class RequestMetrics:
    """Metrics collected during HTTP requests."""

    attempts: list[dict[str, Any]] = field(default_factory=list)
    total_duration: float = 0.0


class RetryableHTTPError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        self.attempts = attempts
        super().__init__(f"Failed after {len(attempts)} attempts")


class RetryableHTTPClient:
    """HTTP client with retry logic and exponential backoff.

    Implements retry with exponential backoff: base_delay * 2^n with jitter.

    Attributes:
        client: Underlying httpx.AsyncClient
        rate_limiter: Token bucket rate limiter
        retry_config: Retry behavior configuration
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: TokenBucketRateLimiter,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self.client = client
        self.rate_limiter = rate_limiter
        self.retry_config = retry_config or RetryConfig()
        self.metrics = RequestMetrics()

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate backoff delay with jitter."""
        import random

        base = self.retry_config.base_delay * (2**attempt)
        jitter = random.uniform(-self.retry_config.jitter, self.retry_config.jitter)
        return min(base + jitter, self.retry_config.max_delay)

    def _is_retryable(self, status_code: int | None) -> bool:
        """Check if a status code is retryable."""
        if status_code is None:
            return True
        return status_code in self.retry_config.retryable_statuses

    async def _attempt_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute a single HTTP request."""
        start = time.perf_counter()
        response = await self.client.request(method, url, **kwargs)
        duration = time.perf_counter() - start

        attempt_info = {
            "method": method,
            "url": url,
            "status_code": response.status_code,
            "duration": duration,
        }
        self.metrics.attempts.append(attempt_info)

        return response

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with rate limiting and retry logic.

        Every attempt (including retries) consumes a rate limit token, as APIs
        typically count all outgoing requests against rate limits.
        """
        for attempt in range(self.retry_config.max_attempts):
            await self.rate_limiter.acquire()
            response = await self._attempt_request(method, url, **kwargs)

            if response.is_success:
                return response

            if not self._is_retryable(response.status_code):
                raise RetryableHTTPError(self.metrics.attempts)

            if attempt < self.retry_config.max_attempts - 1:
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

        raise RetryableHTTPError(self.metrics.attempts)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", url, **kwargs)

    async def close(self) -> None:
        """Close the underlying client."""
        await self.client.aclose()


@pytest.fixture
def retry_config() -> RetryConfig:
    """Default retry configuration for tests."""
    return RetryConfig(
        max_attempts=3,
        base_delay=0.1,
        max_delay=1.0,
        jitter=0.05,
        retryable_statuses=(500, 502, 503, 504),
    )


@pytest.fixture
def retry_config_with_429() -> RetryConfig:
    """Retry configuration that includes 429 (rate limited)."""
    return RetryConfig(
        max_attempts=3,
        base_delay=0.1,
        max_delay=1.0,
        jitter=0.05,
        retryable_statuses=(429, 500, 502, 503, 504),
    )


@pytest.fixture
def mock_http_client(
    mock_httpx_client: Any,
    tracking_rate_limiter: TokenBucketRateLimiter,
    retry_config: RetryConfig,
) -> RetryableHTTPClient:
    """Provide a retryable HTTP client with mocked transport."""
    return RetryableHTTPClient(
        client=mock_httpx_client,
        rate_limiter=tracking_rate_limiter,
        retry_config=retry_config,
    )


@pytest.fixture
def transient_failure_sequence() -> list[int]:
    """Sequence of status codes: 503, then success."""
    return [503, 200]


@pytest.fixture
def persistent_failure_sequence() -> list[int]:
    """Sequence of status codes: all failures."""
    return [503, 503, 503]
