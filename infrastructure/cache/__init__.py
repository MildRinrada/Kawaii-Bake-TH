"""Cache infrastructure - public API."""

from __future__ import annotations

from infrastructure.cache.base import RateLimiter, RateLimitStatus
from infrastructure.cache.redis_cache import CacheRateLimiter


def get_rate_limiter() -> RateLimiter:
    """Return the configured rate limiter.

    Returns:
        A :class:`RateLimiter` implementation.
    """
    return CacheRateLimiter()


__all__ = ["RateLimiter", "RateLimitStatus", "CacheRateLimiter", "get_rate_limiter"]
