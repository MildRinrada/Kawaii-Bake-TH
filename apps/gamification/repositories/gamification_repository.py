"""Write operations for the XP ledger and the derived rows.

The ledger gets an append only. The two derived rows (level, streak) get a
full overwrite  they are recomputed aggregates, so "update" here means
"replace with the freshly derived truth", never arithmetic on stored state.
"""

from __future__ import annotations

from datetime import date

from apps.gamification.models import DailyStreak, UserLevel, XPTransaction


def append_xp(
    *,
    user_id: int,
    reason: str,
    points: int,
    metadata: dict | None = None,
) -> XPTransaction:
    """Append one earning event to the ledger.

    Args:
        user_id: Primary key of the user.
        reason: A value of :class:`XPReason`.
        points: XP earned by this event (positive).
        metadata: Context for the earning event.

    Returns:
        The saved ledger entry.
    """
    return XPTransaction.objects.create(
        user_id=user_id, reason=reason, points=points, metadata=metadata or {}
    )


def store_level(
    *, user_id: int, current_level: int, current_xp: int, total_xp: int
) -> UserLevel:
    """Replace the user's level row with freshly derived values.

    Args:
        user_id: Primary key of the user.
        current_level: The derived level.
        current_xp: XP accumulated inside the current level.
        total_xp: The ledger sum.

    Returns:
        The stored row.
    """
    row, _created = UserLevel.objects.update_or_create(
        user_id=user_id,
        defaults={
            "current_level": current_level,
            "current_xp": current_xp,
            "total_xp": total_xp,
        },
    )
    return row


def store_streak(
    *,
    user_id: int,
    current_streak: int,
    longest_streak: int,
    last_activity_date: date | None,
) -> DailyStreak:
    """Replace the user's streak row with freshly derived values.

    Args:
        user_id: Primary key of the user.
        current_streak: Consecutive days ending today/yesterday.
        longest_streak: Longest run in the full history.
        last_activity_date: The most recent activity day.

    Returns:
        The stored row.
    """
    row, _created = DailyStreak.objects.update_or_create(
        user_id=user_id,
        defaults={
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "last_activity_date": last_activity_date,
        },
    )
    return row
