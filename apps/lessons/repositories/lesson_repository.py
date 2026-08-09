"""Write-side database access for lessons.

**This module is the single choke point for lesson mutations**, and therefore
the only caller of ``course_service.sync_published_lesson_count``. Routing
every create/update/delete/reorder through here is what keeps the counter on
``Course`` from drifting — a mutation path that bypasses this module is a bug
by definition. ``manage.py recount_lessons`` reconciles if one ever ships.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from apps.courses.services import course_service
from apps.lessons.constants import LessonStatus
from apps.lessons.models import Lesson


def _sync_counter(*, course_id: int) -> None:
    """Push the published-lesson count and total duration to the courses app."""
    stats = Lesson.objects.filter(
        course_id=course_id, status=LessonStatus.PUBLISHED
    ).aggregate(count=Count("id"), duration=Coalesce(Sum("duration_minutes"), 0))
    course_service.sync_published_lesson_count(
        course_id=course_id,
        count=stats["count"],
        duration_minutes=stats["duration"],
    )


def next_position(*, course_id: int) -> int:
    """Return the append position for a new lesson.

    Positions are dense, so the count is the next free slot.
    """
    return Lesson.objects.filter(course_id=course_id).count()


def create_lesson(*, course_id: int, **fields: Any) -> Lesson:
    """Create a lesson at the end of its course.

    Args:
        course_id: Primary key of the owning course.
        **fields: Lesson field values.

    Returns:
        The created lesson.
    """
    with transaction.atomic():
        lesson = Lesson.objects.create(
            course_id=course_id,
            position=next_position(course_id=course_id),
            **fields,
        )
        _sync_counter(course_id=course_id)
    return lesson


def update_lesson(*, lesson: Lesson, changes: Mapping[str, Any]) -> Lesson:
    """Apply changes to a lesson in a single UPDATE.

    Args:
        lesson: The lesson to update.
        changes: Field name to new value.

    Returns:
        The updated lesson.
    """
    if not changes:
        return lesson

    with transaction.atomic():
        for field, value in changes.items():
            setattr(lesson, field, value)
        lesson.save(update_fields=[*changes.keys(), "updated_at"])
        if "status" in changes:
            _sync_counter(course_id=lesson.course_id)
    return lesson


def delete_lesson(*, lesson: Lesson) -> None:
    """Delete a lesson and renumber the survivors to keep positions dense.

    Args:
        lesson: The lesson to delete.
    """
    course_id = lesson.course_id
    with transaction.atomic():
        lesson.delete()
        survivors = list(
            Lesson.objects.filter(course_id=course_id).order_by("position", "id")
        )
        for index, survivor in enumerate(survivors):
            survivor.position = index
        Lesson.objects.bulk_update(survivors, ["position"])
        _sync_counter(course_id=course_id)


def reorder_lessons(*, course_id: int, ordered_ids: Sequence[int]) -> None:
    """Renumber a course's lessons to match ``ordered_ids``.

    The caller has already validated that ``ordered_ids`` is exactly the
    course's lesson-id set. One ``bulk_update``; last write wins on the whole
    array, so concurrent reorders can never interleave into a corrupt order.

    Args:
        course_id: Primary key of the course.
        ordered_ids: Every lesson id of the course, in the desired order.
    """
    index_by_id = {lesson_id: index for index, lesson_id in enumerate(ordered_ids)}
    lessons = list(Lesson.objects.filter(course_id=course_id))
    for lesson in lessons:
        lesson.position = index_by_id[lesson.pk]

    with transaction.atomic():
        Lesson.objects.bulk_update(lessons, ["position"])
