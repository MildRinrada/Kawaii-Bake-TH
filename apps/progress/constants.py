"""Enumerations for the progress app."""

from __future__ import annotations

from django.db import models


class ActivityType(models.TextChoices):
    """What kind of learning activity a day-row records.

    ``QUIZ_COMPLETED`` and ``RECIPE_CREATED`` are declared for the schema's
    future consumers; only ``LESSON_COMPLETED`` is recorded in Phase 6 —
    wiring the others requires the producing apps to call this one, which
    the current dependency direction forbids (quizzes ← progress would
    cycle). That wiring is a future phase's problem, recorded in ADR 0012.
    """

    LESSON_COMPLETED = "lesson_completed", "Lesson completed"
    QUIZ_COMPLETED = "quiz_completed", "Quiz completed"
    RECIPE_CREATED = "recipe_created", "Recipe created"
