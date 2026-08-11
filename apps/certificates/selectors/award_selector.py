"""Read-side queries over the earned-achievement ledger for staff.

The ledger itself is append-only (ADR 0012); this module only reads it,
across users, for the ``IsAdminUser``-gated views - which is why it may
join the profile, unlike the owner-scoped reads in the service.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.certificates.models import Achievement


def list_awards(
    *, search: str = "", achievement_type: str = ""
) -> QuerySet[Achievement]:
    """Return the award ledger, newest first.

    Args:
        search: Matches the earner's username or display name.
        achievement_type: Restrict to one achievement type.

    Returns:
        A lazy queryset with user, profile and badge preloaded.
    """
    queryset = Achievement.objects.select_related("user__profile", "badge")

    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(user__username__icontains=cleaned)
            | Q(user__profile__display_name__icontains=cleaned)
        )
    if achievement_type:
        queryset = queryset.filter(achievement_type=achievement_type)

    return queryset.order_by("-awarded_at")
