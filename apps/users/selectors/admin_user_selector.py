"""Read-side queries for the staff user roster.

Every function here serves the ``IsAdminUser``-gated views only; nothing
in this module is reachable from a public endpoint, which is why it may
select PII (email, legal name) that public selectors never touch.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.users.models import User

ROSTER_ORDERINGS: dict[str, tuple[str, ...]] = {
    "newest": ("-created_at",),
    "oldest": ("created_at",),
    "username": ("username",),
    "recently_active": ("-last_login", "-created_at"),
}


def list_users(
    *,
    search: str = "",
    account_status: str = "",
    verified: bool | None = None,
    staff: bool | None = None,
    joined_days: int | None = None,
    ordering: str = "newest",
) -> QuerySet[User]:
    """Return the filtered user roster with profiles preloaded.

    Args:
        search: Matches username, email, legal name or display name.
        account_status: ``active`` or ``suspended``; empty means both.
        verified: Filter on email verification, or ``None`` for both.
        staff: Filter on the staff flag, or ``None`` for both.
        joined_days: Restrict to accounts created within the trailing
            window - the "new users" dashboard figure.
        ordering: One of :data:`ROSTER_ORDERINGS`; unknown keys fall back
            to newest-first.

    Returns:
        A lazy queryset of users with ``profile`` selected.
    """
    queryset = User.objects.select_related("profile")

    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(username__icontains=cleaned)
            | Q(email__icontains=cleaned)
            | Q(first_name__icontains=cleaned)
            | Q(last_name__icontains=cleaned)
            | Q(profile__display_name__icontains=cleaned)
        )

    if account_status == "active":
        queryset = queryset.filter(is_active=True)
    elif account_status == "suspended":
        queryset = queryset.filter(is_active=False)

    if verified is not None:
        queryset = queryset.filter(is_email_verified=verified)
    if staff is not None:
        queryset = queryset.filter(is_staff=staff)
    if joined_days is not None:
        queryset = queryset.filter(
            created_at__gte=timezone.now() - timedelta(days=joined_days)
        )

    return queryset.order_by(*ROSTER_ORDERINGS.get(ordering, ("-created_at",)))


def get_user(*, user_id: int) -> User | None:
    """Fetch one user with profile for the staff detail panel.

    Args:
        user_id: The user's primary key.

    Returns:
        The user, or ``None`` when absent.
    """
    return User.objects.select_related("profile").filter(pk=user_id).first()
