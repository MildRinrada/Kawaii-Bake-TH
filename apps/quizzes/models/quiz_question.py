"""The quiz ↔ question composition rows."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.quizzes.constants import DEFAULT_QUESTION_POINTS


class QuizQuestion(TimeStampedModel):
    """One question's placement in one quiz.

    **Nothing references these rows** — attempt answers point at the bank
    ``Question`` directly — so the whole-collection-replace write pattern is
    safe here, unlike lessons (where progress rows made it destructive).
    Replacing the composition destroys no history because attempts snapshot
    everything they need (order and ``points_possible``) at start.

    ``question`` is ``PROTECT``: deleting a bank question a quiz still uses
    must fail loudly (mapped to 409 ``question_in_use``), never silently
    reshape someone's published quiz.

    ``points`` (default 1) is the weighted-scoring seam: scoring already sums
    it, so future weights are an API change, not a schema or engine change.
    """

    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.CASCADE,
        related_name="quiz_questions",
    )
    question = models.ForeignKey(
        "questions.Question",
        on_delete=models.PROTECT,
        related_name="quiz_placements",
    )
    position = models.PositiveSmallIntegerField(default=0)
    points = models.PositiveSmallIntegerField(default=DEFAULT_QUESTION_POINTS)

    class Meta:
        verbose_name = "quiz question"
        verbose_name_plural = "quiz questions"
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("quiz", "question"), name="quizzes_unique_placement"
            ),
        ]
        indexes = [
            models.Index(fields=["quiz", "position"], name="quizzes_composition_idx"),
        ]

    def __str__(self) -> str:
        """Return the placement description."""
        return f"quiz {self.quiz_id} · question {self.question_id} @ {self.position}"
