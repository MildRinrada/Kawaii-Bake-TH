"""The public leaderboard."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.gamification.models import UserLevel
from apps.gamification.selectors import gamification_selector


def top_users() -> QuerySet[UserLevel]:
    """The leaderboard queryset, highest total XP first.

    Lazy — the paginator slices it at the API edge. Only users with a
    derived level row appear; the row exists precisely so this sort never
    sums ledgers.

    Returns:
        An unevaluated queryset with each row's user preloaded.
    """
    return gamification_selector.leaderboard_queryset()
