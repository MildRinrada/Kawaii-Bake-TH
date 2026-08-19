"""Learner progress business logic.

All completion computation lives here. Course completion is **write-through
with a self-healing read** (the Phase 3 mechanism, now owned by this app):
the completing write recalculates, and the progress read recalculates again,
closing the race where the last two lessons complete concurrently and
neither write sees 100%. Both paths funnel through
:func:`recalculate_course_progress`, which stamps this domain's own
``CourseProgress.completed_at`` **and** notifies the courses app through its
public API so enrollment state stays what Phase 3 promised.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction

from apps.courses.selectors import course_selector, enrollment_selector
from apps.courses.selectors.enrollment_selector import EnrollmentRef
from apps.courses.services import enrollment_service
from apps.lessons.selectors import lesson_selector
from apps.lessons.selectors.lesson_selector import LessonRef
from apps.progress.constants import ActivityType
from apps.progress.exceptions import (
    EnrollmentRequiredError,
    ProgressCourseNotFoundError,
    ProgressLessonNotFoundError,
)
from apps.progress.models import LessonProgress
from apps.progress.repositories import progress_repository
from apps.progress.selectors import progress_selector

logger = logging.getLogger("kawaiibake.progress")


@dataclass(frozen=True)
class LessonProgressItem:
    """One syllabus row merged with the viewer's progress."""

    id: int
    title: str
    position: int
    duration_minutes: int
    is_preview: bool
    completed: bool
    completed_at: datetime | None
    first_completed_at: datetime | None


@dataclass(frozen=True)
class CourseProgressReport:
    """A student's aggregate progress through one course."""

    course_slug: str
    course_title: str
    enrollment: EnrollmentRef
    total_lessons: int
    completed_lessons: int
    percent: int
    completed_at: datetime | None
    lessons: list[LessonProgressItem]


@dataclass(frozen=True)
class MyCourseProgress:
    """One row of the ``/me/progress/`` overview."""

    id: int
    slug: str
    title: str
    completed_lessons: int
    total_lessons: int
    percentage: int
    completed_at: datetime | None
    # The raw `ImageFieldFile`, not a URL - building an absolute URL needs
    # the request, which belongs to the serializer, not this layer.
    thumbnail: Any


def _require_enrolled_lesson(*, lesson_id: int, user_id: int) -> LessonRef:
    """Resolve a lesson the user may record progress on.

    Layer 1 (**404**): the lesson exists for this viewer  the lessons app's
    own visibility rule, via its public ref selector. Layer 2 (**403**):
    an access-granting enrollment. Completion is a course activity, so it
    requires enrollment even on preview lessons  reading is free, progress
    is not.

    Raises:
        ProgressLessonNotFoundError: Layer 1 failure.
        EnrollmentRequiredError: Layer 2 failure.
    """
    lesson = lesson_selector.get_lesson_ref(lesson_id=lesson_id, viewer_id=user_id)
    if lesson is None:
        raise ProgressLessonNotFoundError

    enrollment = enrollment_selector.get_enrollment(
        user_id=user_id, course_id=lesson.course_id
    )
    if enrollment is None or not enrollment.grants_access:
        raise EnrollmentRequiredError
    return lesson


def complete_lesson(
    *, user_id: int, lesson_id: int
) -> tuple[LessonProgress, bool]:
    """Mark a lesson complete. Idempotent.

    One transaction: the progress row, the course recalculation, and the
    day's activity fact commit together.

    Args:
        user_id: Primary key of the student.
        lesson_id: Primary key of the lesson.

    Returns:
        The progress row and whether the course is (now) complete.

    Raises:
        ProgressLessonNotFoundError: If the lesson is hidden or absent.
        EnrollmentRequiredError: If not actively enrolled.
    """
    lesson = _require_enrolled_lesson(lesson_id=lesson_id, user_id=user_id)

    with transaction.atomic():
        progress = progress_repository.get_or_create_lesson_progress(
            user_id=user_id, lesson_id=lesson.id
        )
        progress = progress_repository.mark_completed(progress=progress)
        course_completed = recalculate_course_progress(
            user_id=user_id, course_id=lesson.course_id
        )
        progress_repository.record_activity(
            user_id=user_id, activity_type=ActivityType.LESSON_COMPLETED
        )

    logger.info(
        "lesson_completed user_id=%s lesson_id=%s course_completed=%s",
        user_id,
        lesson.id,
        course_completed,
    )
    return progress, course_completed


def uncomplete_lesson(*, user_id: int, lesson_id: int) -> LessonProgress:
    """Clear a lesson's completion; ``first_completed_at`` history survives.

    Deliberately does **not** clear course completion or downgrade the
    enrollment  completion is a durable fact stamped once (certificates may
    reference it), matching the never-auto-downgrade rule for added lessons.

    Args:
        user_id: Primary key of the student.
        lesson_id: Primary key of the lesson.

    Returns:
        The updated progress row.
    """
    lesson = _require_enrolled_lesson(lesson_id=lesson_id, user_id=user_id)

    progress = progress_repository.get_or_create_lesson_progress(
        user_id=user_id, lesson_id=lesson.id
    )
    return progress_repository.clear_completed(progress=progress)


def recalculate_course_progress(*, user_id: int, course_id: int) -> bool:
    """Derive course completion from lesson completion. The only writer.

    Aggregates this app's rows against the lessons app's published set (its
    public selector). When every required lesson is complete, stamps
    ``CourseProgress.completed_at`` (once, conditionally) and records the
    fact on the courses side through ``record_course_completion``  the
    Phase 3 contract, unchanged. Never un-stamps.

    Args:
        user_id: Primary key of the student.
        course_id: Primary key of the course.

    Returns:
        Whether the course is complete after recalculation.
    """
    required = lesson_selector.published_lesson_ids(course_id=course_id)
    if not required:
        return False

    completed = progress_selector.completed_count_for_course(
        user_id=user_id, course_id=course_id
    )
    if completed < len(required):
        return False

    progress_repository.get_or_create_course_progress(
        user_id=user_id, course_id=course_id
    )
    progress_repository.stamp_course_completed(user_id=user_id, course_id=course_id)
    enrollment_service.record_course_completion(user_id=user_id, course_id=course_id)
    return True


def get_course_progress(
    *, course_slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> CourseProgressReport:
    """Aggregate a student's progress through one course.

    Resolves the course through the courses app's visibility (archived stays
    readable to the enrolled  their rule, composed, not copied), gates on
    enrollment exactly like lesson content, and is the **self-healing half**
    of course completion.

    Args:
        course_slug: Slug of the course.
        viewer_id: Primary key of the viewer.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The aggregate report.

    Raises:
        ProgressCourseNotFoundError: If the course is absent or hidden.
        EnrollmentRequiredError: If the viewer has no access-granting
            enrollment (instructors and staff have no progress; the syllabus
            serves them).
    """
    course = course_selector.get_course_ref(
        slug=course_slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course is None:
        raise ProgressCourseNotFoundError

    enrollment = enrollment_selector.get_enrollment(
        user_id=viewer_id, course_id=course.id
    )
    if enrollment is None or not enrollment.grants_access:
        # A dropped student keeps their history in the database but does not
        # see it until they re-enroll  the same gate as lesson content.
        raise EnrollmentRequiredError

    lessons = lesson_selector.list_published_refs(course_id=course.id)
    rows = {
        row.lesson_id: row
        for row in progress_selector.progress_for_course(
            user_id=viewer_id, course_id=course.id
        )
    }

    items = [
        LessonProgressItem(
            id=lesson.id,
            title=lesson.title,
            position=lesson.position,
            duration_minutes=lesson.duration_minutes,
            is_preview=lesson.is_preview,
            completed=(row := rows.get(lesson.id)) is not None
            and row.completed_at is not None,
            completed_at=row.completed_at if row else None,
            first_completed_at=row.first_completed_at if row else None,
        )
        for lesson in lessons
    ]

    total = len(items)
    completed = sum(1 for item in items if item.completed)
    percent = round(completed * 100 / total) if total else 0

    if total and completed == total:
        # Self-healing: the write-through in complete_lesson missed the race.
        recalculate_course_progress(user_id=viewer_id, course_id=course.id)
        enrollment = enrollment_selector.get_enrollment(
            user_id=viewer_id, course_id=course.id
        )

    completion = progress_selector.course_completion_map(
        user_id=viewer_id, course_ids=[course.id]
    ).get(course.id)

    return CourseProgressReport(
        course_slug=course.slug,
        course_title=course.title,
        enrollment=enrollment,
        total_lessons=total,
        completed_lessons=completed,
        percent=percent,
        completed_at=completion.completed_at if completion else None,
        lessons=items,
    )


def get_my_progress(*, user_id: int) -> list[MyCourseProgress]:
    """The learner's progress across every enrolled course.

    Flat query count regardless of course count: enrolled ids, the course
    cards, one grouped completed-count aggregate, one completion-map fetch 
    merged in Python. ``total_lessons`` reads ``published_lesson_count``,
    the counter the lessons app already maintains on Course (ADR 0009), so
    no lesson rows are counted here.

    Args:
        user_id: Primary key of the learner.

    Returns:
        Per-course summaries, most recently enrolled first.
    """
    course_ids = list(
        enrollment_selector.list_enrolled_course_ids(user_id=user_id)
    )
    if not course_ids:
        return []

    courses = list(
        course_selector.list_viewable_by_ids(ids=course_ids, viewer_id=user_id)
    )
    completed_counts = progress_selector.completed_counts_by_course(
        user_id=user_id, course_ids=course_ids
    )
    completions = progress_selector.course_completion_map(
        user_id=user_id, course_ids=course_ids
    )

    reports = []
    for course in courses:
        total = course.published_lesson_count
        done = min(completed_counts.get(course.pk, 0), total) if total else 0
        completion = completions.get(course.pk)
        reports.append(
            MyCourseProgress(
                id=course.pk,
                slug=course.slug,
                title=course.title,
                completed_lessons=done,
                total_lessons=total,
                percentage=round(done * 100 / total) if total else 0,
                completed_at=completion.completed_at if completion else None,
                thumbnail=course.thumbnail if course.thumbnail else None,
            )
        )
    return reports
