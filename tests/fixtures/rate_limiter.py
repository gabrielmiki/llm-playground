"""Rate limiter fixture for testing API rate limiting behavior."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

import pytest

T = TypeVar("T")


@dataclass
class RateLimiterState:
    """Tracks rate limiter state for assertions."""

    requests_made: list[float] = field(default_factory=list)
    delays_encountered: list[float] = field(default_factory=list)
    last_request_time: float = 0.0


class TokenBucketRateLimiter:
    """Token bucket rate limiter for testing.

    Attributes:
        rate: Tokens per second (e.g., 1.0 = 60/min)
        capacity: Maximum burst size
    """

    def __init__(self, rate: float = 1.0, capacity: int | None = None) -> None:
        self.rate = rate
        self.capacity = capacity or int(rate)
        self.tokens = float(self.capacity)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
        self.state = RateLimiterState()

    async def acquire(self) -> None:
        """Acquire permission to make a request, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                self.state.delays_encountered.append(wait_time)
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1.0

            self.state.requests_made.append(time.monotonic())

    async def throttled_request(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function after acquiring rate limit permission."""
        await self.acquire()
        return await func(*args, **kwargs)


@pytest.fixture
def rate_limiter() -> TokenBucketRateLimiter:
    """Provide a rate limiter configured for Finnhub (60 req/min = 1 req/sec)."""
    return TokenBucketRateLimiter(rate=1.0, capacity=1)


@pytest.fixture
def configurable_rate_limiter() -> Callable[[float, int], TokenBucketRateLimiter]:
    """Factory to create rate limiters with custom rate and capacity."""

    def _create(rate: float, capacity: int | None = None) -> TokenBucketRateLimiter:
        return TokenBucketRateLimiter(rate=rate, capacity=capacity)

    return _create


@pytest.fixture
def tracking_rate_limiter() -> TokenBucketRateLimiter:
    """Provide a rate limiter that tracks all requests for assertion."""
    return TokenBucketRateLimiter(rate=1.0, capacity=60)
