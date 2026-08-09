"""Read-side queries for badge definitions.

Badge definitions are system-owned *display* metadata: seeded by migration,
curated in Django admin, never written through the API. This selector is
the read side of that — it exists so a client can present the achievements
a learner has **not** earned yet, which is impossible from the earned
ledger alone (ADR 0024).
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.certificates.models import BadgeDefinition


def list_active() -> QuerySet[BadgeDefinition]:
    """Every badge the platform currently presents, in slug order.

    Deactivated badges are excluded: switching one off hides it from the
    catalogue without un-earning anyone's achievement, which is the whole
    point of the ``is_active`` flag.

    Returns:
        A lazy queryset of active badge definitions.
    """
    return BadgeDefinition.objects.filter(is_active=True)
