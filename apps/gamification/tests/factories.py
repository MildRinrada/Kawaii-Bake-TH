"""Test data builders for the gamification domain."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.progress.constants import ActivityType
from apps.progress.models import LearningActivity


def add_activity_day(
    *, user: Any, activity_date: date, activity_type: str = ActivityType.LESSON_COMPLETED
) -> LearningActivity:
    """Plant one day-fact in progress' activity ledger.

    Streak derivation consumes exactly these rows; tests write them
    directly to control the calendar.
    """
    activity, _created = LearningActivity.objects.get_or_create(
        user=user, activity_date=activity_date, activity_type=activity_type
    )
    return activity
