"""Rate limiter backed by Django's cache framework.

The concrete store comes from ``settings.CACHES``  Redis in production,
local memory in development and tests  so this adapter never imports a client.
"""

from __future__ import annotations

from django.core.cache import cache

from infrastructure.cache.base import RateLimitStatus

KEY_PREFIX = "ratelimit"


class CacheRateLimiter:
    """Fixed-window counter stored in the configured cache backend."""

    def _cache_key(self, key: str) -> str:
        """Return the namespaced cache key for ``key``."""
        return f"{KEY_PREFIX}:{key}"

    def hit(self, key: str, *, limit: int, window: int) -> RateLimitStatus:
        """Record an attempt against ``key``.

        Args:
            key: Identifier for the counter (for example ``"login:ip:1.2.3.4"``).
            limit: Maximum attempts permitted within the window.
            window: Window length in seconds.

        Returns:
            The resulting :class:`RateLimitStatus`.
        """
        cache_key = self._cache_key(key)
        if cache.add(cache_key, 1, timeout=window):
            current = 1
        else:
            try:
                current = cache.incr(cache_key)
            except ValueError:
                # The entry expired between `add` and `incr`; start a new window.
                cache.set(cache_key, 1, timeout=window)
                current = 1
        return RateLimitStatus(allowed=current <= limit, current=current, limit=limit)

    def peek(self, key: str, *, limit: int) -> RateLimitStatus:
        """Report the counter for ``key`` without incrementing it."""
        current = cache.get(self._cache_key(key), 0)
        return RateLimitStatus(allowed=current < limit, current=current, limit=limit)

    def reset(self, key: str) -> None:
        """Clear the counter for ``key`` (called after a successful login)."""
        cache.delete(self._cache_key(key))
