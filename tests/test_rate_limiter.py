"""Tests for rate limiter implementation."""

from __future__ import annotations

import asyncio

import pytest

from src.collect.rate_limiter import (
    RateLimitConfig,
    TokenBucketRateLimiter,
    create_finnhub_limiter,
)


class TestRateLimitConfig:
    def test_default_values(self) -> None:
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_second == 1.0
        assert config.capacity == 60

    def test_custom_requests_per_minute(self) -> None:
        config = RateLimitConfig(requests_per_minute=120)
        assert config.requests_per_second == 2.0

    def test_burst_size(self) -> None:
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        assert config.capacity == 10

    def test_burst_size_defaults_to_requests_per_minute(self) -> None:
        config = RateLimitConfig(requests_per_minute=30)
        assert config.capacity == 30


class TestTokenBucketRateLimiter:
    @pytest.fixture
    def limiter(self) -> TokenBucketRateLimiter:
        return TokenBucketRateLimiter(config=RateLimitConfig(requests_per_minute=60))

    @pytest.mark.asyncio
    async def test_acquire_consumes_token(
        self, limiter: TokenBucketRateLimiter
    ) -> None:
        await limiter.acquire()
        assert len(limiter.state.requests_made) == 1

    @pytest.mark.asyncio
    async def test_acquire_respects_rate_limit_after_burst(self) -> None:
        limiter = TokenBucketRateLimiter(config=RateLimitConfig(requests_per_minute=60))
        for _ in range(60):
            await limiter.acquire()

        first_request_time = limiter.state.requests_made[0]

        await limiter.acquire()
        last_request_time = limiter.state.requests_made[-1]

        delta = last_request_time - first_request_time
        assert delta >= 0.9

    @pytest.mark.asyncio
    async def test_try_acquire_returns_true_when_available(self) -> None:
        limiter = TokenBucketRateLimiter(config=RateLimitConfig(requests_per_minute=60))
        result = await limiter.try_acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_try_acquire_returns_false_when_no_tokens(self) -> None:
        limiter = TokenBucketRateLimiter(
            config=RateLimitConfig(requests_per_minute=60, burst_size=1)
        )
        await limiter.acquire()
        result = await limiter.try_acquire()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_wait_time_zero_when_available(self) -> None:
        limiter = TokenBucketRateLimiter(config=RateLimitConfig(requests_per_minute=60))
        wait = limiter.get_wait_time()
        assert wait == 0.0

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self) -> None:
        limiter = TokenBucketRateLimiter(
            config=RateLimitConfig(requests_per_minute=6000)
        )

        async def make_request() -> None:
            await limiter.acquire()

        await asyncio.gather(*[make_request() for _ in range(10)])
        assert len(limiter.state.requests_made) == 10


class TestCreateFinnhubLimiter:
    def test_creates_limiter_with_60_rpm(self) -> None:
        limiter = create_finnhub_limiter()
        assert limiter.config.requests_per_minute == 60
        assert limiter.config.requests_per_second == 1.0
