"""Test data builders for the lesson domain."""

from __future__ import annotations

from itertools import count
from typing import Any

from apps.lessons.constants import LessonStatus
from apps.lessons.models import Lesson
from apps.lessons.repositories import lesson_repository

_sequence = count(1)


def create_lesson(
    *,
    course: Any,
    title: str | None = None,
    status: str = LessonStatus.PUBLISHED,
    via_repository: bool = True,
    **extra: Any,
) -> Lesson:
    """Create a lesson.

    Goes through the repository by default so the course's published-lesson
    counter stays true — exactly as production writes do. Pass
    ``via_repository=False`` only when a test deliberately wants drift.
    """
    index = next(_sequence)
    fields: dict[str, Any] = {
        "title": title or f"Lesson {index}",
        "content": extra.pop("content", "Lesson body."),
        "status": status,
        **extra,
    }
    if via_repository:
        return lesson_repository.create_lesson(course_id=course.pk, **fields)

    position = Lesson.objects.filter(course=course).count()
    return Lesson.objects.create(course=course, position=position, **fields)
