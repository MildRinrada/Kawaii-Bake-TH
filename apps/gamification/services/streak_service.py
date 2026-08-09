"""Streak derivation from progress' append-only day-facts.

Never incremented: every recomputation walks the full distinct-date
history from ``LearningActivity`` (the ledger ADR 0012 built as "the
streak substrate"), so the stored row — including the longest streak — can
always be rebuilt from scratch and can never drift.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.gamification.models import DailyStreak
from apps.gamification.repositories import gamification_repository
from apps.gamification.selectors import gamification_selector
from apps.progress.selectors import progress_selector


def recalculate(*, user_id: int) -> DailyStreak:
    """Derive and store the user's streak standing.

    A streak is **alive** if its newest day is today or yesterday — a
    learner who studied through last night has until tonight to continue,
    so today's not-yet-logged day never kills a streak prematurely.

    Args:
        user_id: Primary key of the user.

    Returns:
        The stored streak row.
    """
    dates = progress_selector.activity_dates(user_id=user_id)  # newest first
    today = timezone.localdate()

    current = 0
    longest = 0
    run = 0
    previous = None
    for day in dates:
        run = run + 1 if previous is not None and previous - day == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    if dates and (today - dates[0]) <= timedelta(days=1):
        # The newest run is still alive; measure it from the top.
        current = 1
        for earlier, later in zip(dates[1:], dates, strict=False):
            if later - earlier != timedelta(days=1):
                break
            current += 1

    return gamification_repository.store_streak(
        user_id=user_id,
        current_streak=current,
        longest_streak=longest,
        last_activity_date=dates[0] if dates else None,
    )


def get_streak(*, user_id: int) -> DailyStreak:
    """The user's stored streak row, deriving it on first read.

    Args:
        user_id: Primary key of the user.

    Returns:
        The streak row (freshly derived if absent).
    """
    row = gamification_selector.get_streak(user_id=user_id)
    return row if row is not None else recalculate(user_id=user_id)
