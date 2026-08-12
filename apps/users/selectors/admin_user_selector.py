"""Read-side queries for the staff user roster.

Every function here serves the ``IsAdminUser``-gated views only; nothing
in this module is reachable from a public endpoint, which is why it may
select PII (email, legal name) that public selectors never touch.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

# Staff-only aggregation seam: the roster annotates activity counts over
# other apps' reverse relations (recipes / enrollments / gallery posts).
# Constants only cross the boundary - no other app's queryset is built
# here, and nothing outside the IsAdminUser views renders these numbers.
from apps.courses.constants import EnrollmentStatus
from apps.users.models import User

ROSTER_ORDERINGS: dict[str, tuple[str, ...]] = {
    "newest": ("-created_at",),
    "oldest": ("created_at",),
    "username": ("username",),
    "recently_active": ("-last_login", "-created_at"),
}


def _with_activity(queryset: QuerySet[User]) -> QuerySet[User]:
    """Annotate the activity counts the roster row displays.

    ``distinct`` keeps each count honest across the multi-join: without
    it, a user with 3 recipes and 2 enrollments would report 6 of each.
    """
    return queryset.annotate(
        recipes_count=Count("recipes", distinct=True),
        courses_count=Count(
            "enrollments",
            filter=Q(
                enrollments__status__in=(
                    EnrollmentStatus.ACTIVE,
                    EnrollmentStatus.COMPLETED,
                )
            ),
            distinct=True,
        ),
        posts_count=Count("gallery_posts", distinct=True),
    )


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
    queryset = _with_activity(User.objects.select_related("profile"))

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
    return (
        _with_activity(User.objects.select_related("profile"))
        .filter(pk=user_id)
        .first()
    )


def roster_stats() -> dict[str, int]:
    """Headline account numbers for the roster's summary cards.

    "Pending" is honest to what the platform records: an active account
    whose email is still unverified.

    Returns:
        Mapping with ``total``, ``active``, ``pending``, ``suspended``,
        ``staff`` and ``new_7d`` counts.
    """
    week_ago = timezone.now() - timedelta(days=7)
    return User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        pending=Count(
            "id", filter=Q(is_active=True, is_email_verified=False)
        ),
        suspended=Count("id", filter=Q(is_active=False)),
        staff=Count("id", filter=Q(is_staff=True)),
        new_7d=Count("id", filter=Q(created_at__gte=week_ago)),
    )
