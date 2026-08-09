"""Read-side queries for the ledger, levels and streaks."""

from __future__ import annotations

from django.db.models import Count, QuerySet, Sum

from apps.gamification.models import DailyStreak, UserLevel, XPTransaction


def get_user_level(*, user_id: int) -> UserLevel | None:
    """Fetch the user's level row, if it has been derived yet.

    Args:
        user_id: Primary key of the user.

    Returns:
        The level row, or ``None``.
    """
    return UserLevel.objects.filter(user_id=user_id).first()


def get_streak(*, user_id: int) -> DailyStreak | None:
    """Fetch the user's streak row, if it has been derived yet.

    Args:
        user_id: Primary key of the user.

    Returns:
        The streak row, or ``None``.
    """
    return DailyStreak.objects.filter(user_id=user_id).first()


def recent_transactions(
    *, user_id: int, limit: int
) -> list[XPTransaction]:
    """The user's newest ledger entries.

    Args:
        user_id: Primary key of the user.
        limit: Maximum entries to return.

    Returns:
        Ledger entries, newest first.
    """
    return list(XPTransaction.objects.filter(user_id=user_id)[:limit])


def total_points(*, user_id: int) -> int:
    """Sum the user's ledger.

    Args:
        user_id: Primary key of the user.

    Returns:
        Total XP earned, 0 for an empty ledger.
    """
    return (
        XPTransaction.objects.filter(user_id=user_id).aggregate(
            total=Sum("points")
        )["total"]
        or 0
    )


def ledger_counts(*, user_id: int) -> dict[str, int]:
    """How many ledger entries exist per reason, in one query.

    The reconciliation input: recalculation compares these against the
    derived fact counts and appends only the difference.

    Args:
        user_id: Primary key of the user.

    Returns:
        Mapping of reason to entry count (absent = zero).
    """
    rows = (
        XPTransaction.objects.filter(user_id=user_id)
        .values("reason")
        .annotate(entries=Count("id"))
    )
    return {row["reason"]: row["entries"] for row in rows}


def leaderboard_queryset() -> QuerySet[UserLevel]:
    """The leaderboard: level rows by total XP, holders preloaded.

    ``select_related`` keeps the page at one query regardless of size —
    the serializer reads only the public handle off the joined row.

    Returns:
        A lazy queryset, highest XP first.
    """
    return UserLevel.objects.select_related("user").order_by("-total_xp", "id")
