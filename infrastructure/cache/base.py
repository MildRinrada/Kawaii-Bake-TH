"""Cache seam — rate limiting primitives.

Auth throttling is deliberately cache-backed rather than table-backed, so no
database table is required to defend the login and password-reset endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RateLimitStatus:
    """Outcome of a rate-limited attempt.

    Attributes:
        allowed: Whether the attempt is within the configured limit.
        current: Number of attempts recorded in the current window.
        limit: Maximum attempts permitted per window.
    """

    allowed: bool
    current: int
    limit: int


class RateLimiter(Protocol):
    """Counts attempts within a sliding expiry window."""

    def hit(self, key: str, *, limit: int, window: int) -> RateLimitStatus:
        """Record an attempt against ``key`` and report whether it is allowed."""
        ...

    def peek(self, key: str, *, limit: int) -> RateLimitStatus:
        """Report the current status of ``key`` without recording an attempt."""
        ...

    def reset(self, key: str) -> None:
        """Clear the counter for ``key``."""
        ...
