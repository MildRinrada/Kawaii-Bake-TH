"""Read-side queries for lessons.

Every query composes the **courses** visibility rule across the join via
``visible_detail_q(prefix="course__")``  one rule, one implementation, applied
on both sides of the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q, QuerySet

from apps.courses.selectors.course_visibility import visible_detail_q
from apps.lessons.constants import LessonStatus
from apps.lessons.models import Lesson


@dataclass(frozen=True)
class LessonRef:
    """A lesson reference safe to hand across the app boundary.

    Added in Phase 6 for the ``progress`` app  the same frozen-ref mechanism
    as ``CourseRef``/``RecipeRef`` (ADR 0009). Carries identity, the owning
    course, and the state pair progress gating needs.
    """

    id: int
    course_id: int
    title: str
    position: int
    duration_minutes: int
    is_preview: bool
    status: str


def _lesson_status_q(*, viewer_id: int | None, viewer_is_staff: bool) -> Q:
    """Restrict to published lessons unless the viewer owns the course."""
    if viewer_is_staff:
        return Q()

    condition = Q(status=LessonStatus.PUBLISHED)
    if viewer_id is not None:
        condition |= Q(course__instructor_id=viewer_id)
    return condition


def list_for_course(
    *,
    course_id: int,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> QuerySet[Lesson]:
    """List a course's lessons for the syllabus.

    The caller has already resolved the course through
    ``course_selector.get_course_ref`` (which applies course visibility), so
    this filters by lesson status only: non-owners see published lessons,
    owner and staff see everything.

    Args:
        course_id: Primary key of the course.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A lazy queryset ordered by position.
    """
    return (
        Lesson.objects.filter(course_id=course_id)
        .filter(_lesson_status_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff))
        .order_by("position", "id")
    )


def get_lesson(
    *,
    lesson_id: int,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> Lesson | None:
    """Fetch one lesson the viewer is allowed to know exists.

    This is the **404 layer**: course visibility (composed across the join) and
    lesson status. Whether the viewer may read the *content* is the separate
    403 layer, decided by the service against enrollment.

    Args:
        lesson_id: Primary key of the lesson.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The lesson with its course loaded, or ``None``.
    """
    return (
        Lesson.objects.filter(pk=lesson_id)
        .filter(
            visible_detail_q(
                viewer_id=viewer_id, viewer_is_staff=viewer_is_staff, prefix="course__"
            )
        )
        .filter(_lesson_status_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff))
        .select_related("course")
        .first()
    )


def get_lesson_ref(
    *,
    lesson_id: int,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> LessonRef | None:
    """Fetch a lesson reference for another app.

    Part of the public cross-app API (Phase 6). Applies the full existence
    layer  course visibility across the join plus lesson status  and
    returns ``None`` when the lesson does not exist for this viewer; the
    caller raises its own domain error, never this app's.

    Args:
        lesson_id: Primary key of the lesson.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A :class:`LessonRef`, or ``None``.
    """
    row = (
        Lesson.objects.filter(pk=lesson_id)
        .filter(
            visible_detail_q(
                viewer_id=viewer_id, viewer_is_staff=viewer_is_staff, prefix="course__"
            )
        )
        .filter(_lesson_status_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff))
        .values(
            "id",
            "course_id",
            "title",
            "position",
            "duration_minutes",
            "is_preview",
            "status",
        )
        .first()
    )
    return LessonRef(**row) if row else None


def list_published_refs(*, course_id: int) -> list[LessonRef]:
    """Return a course's published lessons as refs, in syllabus order.

    Part of the public cross-app API (Phase 6)  the required-lesson set the
    progress app aggregates against. The caller has already resolved the
    course through courses' visibility.

    Args:
        course_id: Primary key of the course.

    Returns:
        Ordered lesson references.
    """
    rows = (
        Lesson.objects.filter(course_id=course_id, status=LessonStatus.PUBLISHED)
        .order_by("position", "id")
        .values(
            "id",
            "course_id",
            "title",
            "position",
            "duration_minutes",
            "is_preview",
            "status",
        )
    )
    return [LessonRef(**row) for row in rows]


def published_lesson_ids(*, course_id: int) -> list[int]:
    """Return the ids of a course's published lessons.

    Args:
        course_id: Primary key of the course.

    Returns:
        Lesson ids in syllabus order.
    """
    return list(
        Lesson.objects.filter(course_id=course_id, status=LessonStatus.PUBLISHED)
        .order_by("position", "id")
        .values_list("id", flat=True)
    )


def lesson_ids_for_course(*, course_id: int) -> set[int]:
    """Return every lesson id of a course, any status.

    Used to validate reorder payloads.

    Args:
        course_id: Primary key of the course.

    Returns:
        The full id set.
    """
    return set(Lesson.objects.filter(course_id=course_id).values_list("id", flat=True))
