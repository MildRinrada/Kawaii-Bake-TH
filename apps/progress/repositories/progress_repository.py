"""Write-side database access for learner progress."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.progress.models import CourseProgress, LearningActivity, LessonProgress


def get_or_create_lesson_progress(*, user_id: int, lesson_id: int) -> LessonProgress:
    """Fetch or create the (user, lesson) row, tolerating a concurrent create.

    Args:
        user_id: Primary key of the user.
        lesson_id: Primary key of the lesson.

    Returns:
        The progress row.
    """
    try:
        with transaction.atomic():
            row, _ = LessonProgress.objects.get_or_create(
                user_id=user_id, lesson_id=lesson_id
            )
            return row
    except IntegrityError:
        return LessonProgress.objects.get(user_id=user_id, lesson_id=lesson_id)


def mark_completed(*, progress: LessonProgress) -> LessonProgress:
    """Complete a lesson. Idempotent.

    ``completed_at`` is set only when currently NULL (a second complete
    returns the existing state untouched); ``first_completed_at`` is stamped
    exactly once, ever.

    Args:
        progress: The row to complete.

    Returns:
        The updated row.
    """
    now = timezone.now()
    changes = ["last_viewed_at", "updated_at"]
    progress.last_viewed_at = now
    if progress.completed_at is None:
        progress.completed_at = now
        changes.append("completed_at")
    if progress.first_completed_at is None:
        progress.first_completed_at = progress.completed_at
        changes.append("first_completed_at")
    progress.save(update_fields=changes)
    return progress


def clear_completed(*, progress: LessonProgress) -> LessonProgress:
    """Un-complete a lesson; ``first_completed_at`` history survives.

    Args:
        progress: The row to clear.

    Returns:
        The updated row.
    """
    progress.last_viewed_at = timezone.now()
    changes = ["last_viewed_at", "updated_at"]
    if progress.completed_at is not None:
        progress.completed_at = None
        changes.append("completed_at")
    progress.save(update_fields=changes)
    return progress


def get_or_create_course_progress(*, user_id: int, course_id: int) -> CourseProgress:
    """Fetch or create the (user, course) anchor row, race-safe.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        The course progress row.
    """
    try:
        with transaction.atomic():
            row, _ = CourseProgress.objects.get_or_create(
                user_id=user_id, course_id=course_id
            )
            return row
    except IntegrityError:
        return CourseProgress.objects.get(user_id=user_id, course_id=course_id)


def stamp_course_completed(*, user_id: int, course_id: int) -> None:
    """Stamp course completion exactly once.

    A conditional UPDATE on ``completed_at IS NULL`` — never re-stamped,
    never cleared, safe under concurrent completing writes.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.
    """
    CourseProgress.objects.filter(
        user_id=user_id, course_id=course_id, completed_at__isnull=True
    ).update(completed_at=timezone.now(), updated_at=timezone.now())


def record_activity(*, user_id: int, activity_type: str) -> None:
    """Record today's activity fact. Idempotent per (user, day, type).

    Args:
        user_id: Primary key of the user.
        activity_type: A value of :class:`ActivityType`.
    """
    try:
        with transaction.atomic():
            LearningActivity.objects.get_or_create(
                user_id=user_id,
                activity_date=timezone.localdate(),
                activity_type=activity_type,
            )
    except IntegrityError:
        pass
