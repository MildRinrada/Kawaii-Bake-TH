"""Attempt throttling for assistant endpoints.

Backed by ``infrastructure.cache`` counters (the auth precedent) — every AI
call costs real money, so the send endpoint is throttled per user before the
provider is ever reached. This is the rate-limiting hook: quota/billing will
later enforce against :class:`AIUsageLog` aggregates in the same place.
"""

from __future__ import annotations

from django.conf import settings

from apps.assistant.constants import RATE_LIMIT_ASSISTANT_MESSAGE
from apps.core.exceptions import RateLimitedError
from infrastructure.cache import get_rate_limiter


def enforce_message_rate_limit(*, user_id: int) -> None:
    """Throttle message sends per user.

    Keyed by user, not IP: the endpoint requires authentication, and the
    cost being protected is per-account provider spend.

    Args:
        user_id: Primary key of the sender.

    Raises:
        RateLimitedError: If the allowance is exhausted.
    """
    status = get_rate_limiter().hit(
        f"{RATE_LIMIT_ASSISTANT_MESSAGE}:{user_id}",
        limit=settings.ASSISTANT_MESSAGE_RATE_LIMIT_ATTEMPTS,
        window=settings.ASSISTANT_MESSAGE_RATE_LIMIT_WINDOW,
    )
    if not status.allowed:
        raise RateLimitedError
