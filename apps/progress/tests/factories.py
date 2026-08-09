"""Test data builders for the progress domain."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.progress.models import LessonProgress


def complete_lesson_row(*, user: Any, lesson: Any, **extra: Any) -> LessonProgress:
    """Create a completed progress row directly at the model layer."""
    stamp = extra.pop("completed_at", timezone.now())
    return LessonProgress.objects.create(
        user=user,
        lesson=lesson,
        completed_at=stamp,
        first_completed_at=extra.pop("first_completed_at", stamp),
        last_viewed_at=stamp,
        **extra,
    )
