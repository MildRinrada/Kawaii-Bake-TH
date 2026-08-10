"""The cached set of currently blocked addresses.

Lives in its own module because two layers legitimately need it and
neither should import the other: the middleware *reads* it on every
request, and the repository *invalidates* it whenever a block is written.
Routing that through either one would couple the request path to the
admin path.
"""

from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

#: How long the set is cached.
#:
#: A block therefore takes up to this long to bite, and up to this long
#: to lift. That lag is the price of not querying the table on every
#: request; the dashboard says so out loud so an operator does not think
#: the button failed. Writes invalidate eagerly, so in practice the lag
#: only appears when a block *lapses* on its own.
CACHE_SECONDS = 30
CACHE_KEY = "security:blocked-ips"


def blocked_ips() -> frozenset[str]:
    """Return the addresses whose block window is still open."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    # Imported lazily: this module is imported from middleware, which is
    # constructed before the app registry is guaranteed ready.
    from apps.security.models import ThreatProfile

    blocked = frozenset(
        ThreatProfile.objects.filter(blocked_until__gt=timezone.now()).values_list(
            "ip", flat=True
        )
    )
    cache.set(CACHE_KEY, blocked, CACHE_SECONDS)
    return blocked


def invalidate() -> None:
    """Drop the cached set so the next request re-reads the table."""
    cache.delete(CACHE_KEY)
