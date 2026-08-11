"""Cross-user progress reads for the staff surface.

Everything else in this app is keyed by a single ``user_id`` - the
learner reading their own progress. These functions cut the other way
(one course, many learners; or the whole platform) and serve only the
``IsAdminUser``-gated views, which is why they may aggregate across
users at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import Count, Max
from django.utils import timezone

from apps.lessons.constants import LessonStatus
from apps.progress.models import LearningActivity, LessonProgress


def completed_counts_for_users(
    *, course_id: int, user_ids: list[int]
) -> dict[int, int]:
    """Completed published-lesson counts per learner, for one course.

    The transpose of ``completed_counts_by_course``: one course, many
    users, one query.

    Args:
        course_id: Primary key of the course.
        user_ids: The learners on the current roster page.

    Returns:
        Mapping of user id to completed count (absent = zero).
    """
    if not user_ids:
        return {}
    rows = (
        LessonProgress.objects.filter(
            user_id__in=user_ids,
            lesson__course_id=course_id,
            lesson__status=LessonStatus.PUBLISHED,
            completed_at__isnull=False,
        )
        .values("user_id")
        .annotate(total=Count("id"))
    )
    return {row["user_id"]: row["total"] for row in rows}


def last_activity_for_users(
    *, course_id: int, user_ids: list[int]
) -> dict[int, datetime]:
    """When each learner last touched this course, one query.

    ``last_viewed_at`` is written on every completion change, so its max
    over the course's lessons is the most recent progress event - the
    signal that separates "still learning" from "went quiet".

    Args:
        course_id: Primary key of the course.
        user_ids: The learners on the current roster page.

    Returns:
        Mapping of user id to the latest activity time (absent = never).
    """
    if not user_ids:
        return {}
    rows = (
        LessonProgress.objects.filter(
            user_id__in=user_ids, lesson__course_id=course_id
        )
        .values("user_id")
        .annotate(latest=Max("last_viewed_at"))
    )
    return {
        row["user_id"]: row["latest"] for row in rows if row["latest"] is not None
    }


def total_completed_lessons() -> int:
    """How many lesson completions exist platform-wide.

    Returns:
        The count of completed lesson-progress rows.
    """
    return LessonProgress.objects.filter(completed_at__isnull=False).count()


def active_learner_count(*, days: int = 7) -> int:
    """Distinct learners with recorded activity in the last ``days`` days.

    Args:
        days: The trailing window length.

    Returns:
        The distinct learner count.
    """
    since = timezone.localdate() - timedelta(days=days)
    return (
        LearningActivity.objects.filter(activity_date__gte=since)
        .values("user_id")
        .distinct()
        .count()
    )
