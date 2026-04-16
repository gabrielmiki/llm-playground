"""Async HTTP client with retry logic and rate limiting."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from src.collect.rate_limiter import TokenBucketRateLimiter

if TYPE_CHECKING:
    from httpx._types import (
        AuthTypes,
        CookieTypes,
        HeaderTypes,
        QueryParamTypes,
        RequestContent,
    )


DEFAULT_RETRYABLE_STATUSES = (429, 500, 502, 503, 504)
DEFAULT_TIMEOUT_CONFIG = httpx.Timeout(30.0, connect=10.0)


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of request attempts (default: 3).
        base_delay: Base delay for exponential backoff in seconds (default: 1.0).
        max_delay: Maximum delay cap in seconds (default: 10.0).
        jitter: Maximum jitter range in seconds (default: 0.5).
        retryable_statuses: HTTP status codes that trigger a retry.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    jitter: float = 0.5
    retryable_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUSES


@dataclass
class RequestMetrics:
    """Metrics collected during HTTP requests.

    Attributes:
        attempts: List of attempt details including method, URL, status, and duration.
        total_duration: Total time spent on all attempts.
    """

    attempts: list[dict[str, Any]] = field(default_factory=list)
    total_duration: float = 0.0


class RetryableHTTPError(Exception):
    """Raised when all retry attempts are exhausted.

    Attributes:
        attempts: List of attempt details from each failed attempt.
    """

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        self.attempts = attempts
        super().__init__(f"Failed after {len(attempts)} attempts")


class RetryableHTTPClient:
    """Async HTTP client with retry logic and rate limiting.

    Combines rate limiting with exponential backoff retry logic to provide
    robust HTTP requests to external APIs. Every attempt (including retries)
    consumes a rate limit token, as APIs typically count all outgoing requests.

    The client manages its own connection pool and ensures proper cleanup
    on close.

    Example:
        ```python
        async with RetryableHTTPClient() as client:
            response = await client.get("https://api.example.com/data")
            print(response.json())
        ```

    Attributes:
        rate_limiter: Token bucket rate limiter for request throttling.
        retry_config: Configuration for retry behavior.
        timeout: HTTP timeout configuration.
    """

    def __init__(
        self,
        rate_limiter: TokenBucketRateLimiter | None = None,
        retry_config: RetryConfig | None = None,
        timeout: httpx.Timeout | None = None,
        limits: httpx.Limits | None = None,
    ) -> None:
        from src.collect.rate_limiter import create_finnhub_limiter

        self._rate_limiter = rate_limiter or create_finnhub_limiter()
        self.retry_config = retry_config or RetryConfig()
        self.timeout = timeout or DEFAULT_TIMEOUT_CONFIG
        self._limits = limits or httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
        )
        self._client: httpx.AsyncClient | None = None
        self.metrics = RequestMetrics()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Lazily initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=self._limits,
            )
        return self._client

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Args:
            attempt: The current attempt number (0-indexed).

        Returns:
            Delay in seconds, capped at max_delay.
        """
        base = self.retry_config.base_delay * (2**attempt)
        jitter = random.uniform(
            -self.retry_config.jitter,
            self.retry_config.jitter,
        )
        return min(base + jitter, self.retry_config.max_delay)

    def _is_retryable(self, status_code: int | None) -> bool:
        """Check if a status code should trigger a retry.

        Args:
            status_code: HTTP status code to check.

        Returns:
            True if the status code is retryable, False otherwise.
        """
        if status_code is None:
            return True
        return status_code in self.retry_config.retryable_statuses

    async def _attempt_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        request_attempts: list[dict[str, Any]],
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute a single HTTP request and record metrics.

        Args:
            client: The httpx AsyncClient to use.
            method: HTTP method (GET, POST, etc.).
            url: Request URL.
            request_attempts: List to accumulate attempt details for this request.
            **kwargs: Additional arguments passed to httpx.request.

        Returns:
            The HTTP response.

        Raises:
            httpx.TimeoutException: If the request times out.
        """
        start = time.perf_counter()
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException:
            raise
        duration = time.perf_counter() - start

        attempt_info = {
            "method": method,
            "url": url,
            "status_code": response.status_code,
            "duration": duration,
        }
        request_attempts.append(attempt_info)

        return response

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        content: RequestContent | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        auth: AuthTypes | None = None,
        cookies: CookieTypes | None = None,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        """Make an HTTP request with rate limiting and retry logic.

        Every attempt (including retries) consumes a rate limit token, as APIs
        typically count all outgoing requests against rate limits.

        Args:
            method: HTTP method.
            url: Request URL.
            params: Query parameters.
            headers: Request headers.
            content: Raw request body.
            data: Form-encoded data.
            json: JSON-encoded body.
            auth: Authentication.
            cookies: Cookies.
            follow_redirects: Whether to follow redirects.

        Returns:
            The HTTP response.

        Raises:
            RetryableHTTPError: If all retry attempts are exhausted.
            httpx.TimeoutException: If the request times out.
        """
        client = await self._ensure_client()
        request_attempts: list[dict[str, Any]] = []
        last_exception: Exception | None = None

        for attempt in range(self.retry_config.max_attempts):
            await self._rate_limiter.acquire()

            try:
                response = await self._attempt_request(
                    client,
                    method,
                    url,
                    request_attempts,
                    params=params,
                    headers=headers,
                    content=content,
                    data=data,
                    json=json,
                    auth=auth,
                    cookies=cookies,
                    follow_redirects=follow_redirects,
                )
            except httpx.TransportError as exc:
                last_exception = exc
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                continue

            if response.is_success:
                return response

            if not self._is_retryable(response.status_code):
                raise RetryableHTTPError(request_attempts)

            if attempt < self.retry_config.max_attempts - 1:
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

        if last_exception is not None:
            raise RetryableHTTPError(request_attempts) from last_exception
        raise RetryableHTTPError(request_attempts)

    async def get(
        self,
        url: str,
        *,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a GET request.

        Args:
            url: Request URL.
            params: Query parameters.
            headers: Request headers.
            **kwargs: Additional arguments.

        Returns:
            The HTTP response.
        """
        return await self.request("GET", url, params=params, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: HeaderTypes | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a POST request.

        Args:
            url: Request URL.
            data: Form-encoded data.
            json: JSON-encoded body.
            headers: Request headers.
            **kwargs: Additional arguments.

        Returns:
            The HTTP response.
        """
        return await self.request(
            "POST",
            url,
            data=data,
            json=json,
            headers=headers,
            **kwargs,
        )

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "RetryableHTTPClient":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager and close client."""
        await self.close()


def create_finnhub_client() -> RetryableHTTPClient:
    """Create an HTTP client configured for Finnhub API.

    Returns:
        RetryableHTTPClient with Finnhub-appropriate settings.
    """
    return RetryableHTTPClient(
        retry_config=RetryConfig(max_attempts=3),
    )
