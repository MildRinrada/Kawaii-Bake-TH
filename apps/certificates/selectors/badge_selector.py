"""Read-side queries for badge definitions.

Badge definitions are system-owned *display* metadata: seeded by
migration, curated by staff (through ``/admin/achievements/``), never
written by a public endpoint. This selector is the read side of that  it
exists so a client can present the achievements a learner has **not**
earned yet, which is impossible from the earned ledger alone (ADR 0024).
"""

from __future__ import annotations

from django.db.models import Count, QuerySet

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


def list_all() -> QuerySet[BadgeDefinition]:
    """Every badge, inactive included, for the staff surface.

    ``awarded_count`` is annotated so the admin screen can warn before a
    delete attempt hits the PROTECT constraint.

    Returns:
        Badges annotated with ``awarded_count``, in slug order.
    """
    return BadgeDefinition.objects.annotate(
        awarded_count=Count("achievements", distinct=True)
    )


def get_by_slug(*, slug: str) -> BadgeDefinition | None:
    """Fetch one badge by slug, annotated with ``awarded_count``.

    Args:
        slug: The badge slug.

    Returns:
        The badge, or ``None`` when absent.
    """
    return list_all().filter(slug__iexact=slug.strip()).first()
