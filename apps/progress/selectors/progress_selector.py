"""Read-side queries for learner progress.

Counts are always computed from ``LessonProgress`` rows — there is no stored
counter anywhere in this domain to drift (ADR 0012).
"""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from apps.lessons.constants import LessonStatus
from apps.progress.models import CourseProgress, LearningActivity, LessonProgress


def progress_for_course(*, user_id: int, course_id: int) -> QuerySet[LessonProgress]:
    """The user's progress rows for one course's lessons.

    Traverses this app's own ``lesson`` FK — filtering across an owned
    relation is the join the prefix-Q mechanism exists for.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        A lazy queryset.
    """
    return LessonProgress.objects.filter(user_id=user_id, lesson__course_id=course_id)


def completed_count_for_course(*, user_id: int, course_id: int) -> int:
    """How many **published** lessons of a course the user has completed.

    Draft lessons never count — they are not part of the required set.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        The completed count.
    """
    return LessonProgress.objects.filter(
        user_id=user_id,
        lesson__course_id=course_id,
        lesson__status=LessonStatus.PUBLISHED,
        completed_at__isnull=False,
    ).count()


def completed_counts_by_course(
    *, user_id: int, course_ids: list[int]
) -> dict[int, int]:
    """Completed published-lesson counts per course, in one query.

    The batch shape behind ``/me/progress/`` — no per-course queries.

    Args:
        user_id: Primary key of the user.
        course_ids: Course primary keys.

    Returns:
        Mapping of course id to completed count (absent = zero).
    """
    if not course_ids:
        return {}
    rows = (
        LessonProgress.objects.filter(
            user_id=user_id,
            lesson__course_id__in=course_ids,
            lesson__status=LessonStatus.PUBLISHED,
        )
        .values("lesson__course_id")
        .annotate(
            done=Count("id", filter=Q(completed_at__isnull=False)),
        )
    )
    return {row["lesson__course_id"]: row["done"] for row in rows}


def get_course_completed_at(*, user_id: int, course_id: int):
    """When the user completed a course, or ``None``.

    Part of the public cross-app API (Phase 8) — the completion **fact**
    certificates trust. Reads the stamped ``CourseProgress.completed_at``
    (written once by ``recalculate_course_progress``, never downgraded);
    consumers must never re-derive completion themselves.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        The completion timestamp, or ``None`` if not completed.
    """
    return (
        CourseProgress.objects.filter(
            user_id=user_id, course_id=course_id, completed_at__isnull=False
        )
        .values_list("completed_at", flat=True)
        .first()
    )


def completed_course_count(*, user_id: int) -> int:
    """How many courses the user has completed, ever.

    Part of the public cross-app API (Phase 8) — the count behind
    volume-based achievements (``ten_courses``). Computed live from the
    stamped facts; no counter column exists to drift.

    Args:
        user_id: Primary key of the user.

    Returns:
        The completed-course count.
    """
    return CourseProgress.objects.filter(
        user_id=user_id, completed_at__isnull=False
    ).count()


def completed_lesson_count(*, user_id: int) -> int:
    """How many published lessons the user has completed, ever.

    Part of the public cross-app API (Phase 9) — the per-lesson fact count
    behind XP derivation. Computed live from the stamped rows.

    Args:
        user_id: Primary key of the user.

    Returns:
        The completed-lesson count.
    """
    return LessonProgress.objects.filter(
        user_id=user_id,
        completed_at__isnull=False,
        lesson__status=LessonStatus.PUBLISHED,
    ).count()


def completed_lesson_ids(*, user_id: int) -> list[int]:
    """The published lessons the user has completed, as identities.

    Part of the public cross-app API (Phase 13) — the **identified**
    sibling of :func:`completed_lesson_count`: the rewards ledger keys
    idempotency to the lesson id, so it needs the facts themselves, not
    their count. Same rule (published only, stamped ``completed_at``).

    Args:
        user_id: Primary key of the user.

    Returns:
        Lesson ids, ascending for determinism.
    """
    return list(
        LessonProgress.objects.filter(
            user_id=user_id,
            completed_at__isnull=False,
            lesson__status=LessonStatus.PUBLISHED,
        )
        .order_by("lesson_id")
        .values_list("lesson_id", flat=True)
    )


def completed_course_ids(*, user_id: int) -> list[int]:
    """The courses the user has completed, as identities.

    Part of the public cross-app API (Phase 13) — the identified sibling
    of :func:`completed_course_count`, reading the same stamped fact.

    Args:
        user_id: Primary key of the user.

    Returns:
        Course ids, ascending for determinism.
    """
    return list(
        CourseProgress.objects.filter(user_id=user_id, completed_at__isnull=False)
        .order_by("course_id")
        .values_list("course_id", flat=True)
    )


def activity_dates(*, user_id: int) -> list:
    """Every distinct date the user learned something, newest first.

    Part of the public cross-app API (Phase 9) — the day-facts the streak
    derivation consumes. The ledger is append-only (ADR 0012), so this
    list only ever grows.

    Args:
        user_id: Primary key of the user.

    Returns:
        Distinct :class:`datetime.date` values, descending.
    """
    return list(
        LearningActivity.objects.filter(user_id=user_id)
        .order_by("-activity_date")
        .values_list("activity_date", flat=True)
        .distinct()
    )


def course_completion_map(
    *, user_id: int, course_ids: list[int]
) -> dict[int, CourseProgress]:
    """The user's course-progress rows for a set of courses, keyed by course.

    Args:
        user_id: Primary key of the user.
        course_ids: Course primary keys.

    Returns:
        Mapping of course id to :class:`CourseProgress`.
    """
    if not course_ids:
        return {}
    rows = CourseProgress.objects.filter(user_id=user_id, course_id__in=course_ids)
    return {row.course_id: row for row in rows}
