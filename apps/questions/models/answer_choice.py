"""Answer choices for choice-backed questions."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.questions.constants import CHOICE_TEXT_MAX_LENGTH


class AnswerChoice(TimeStampedModel):
    """One selectable answer belonging to a question.

    ``is_correct`` is a **per-field secret**: it must never appear in any
    taker-facing payload. The taker read path therefore goes through DTOs that
    have no such field at all (``selectors/question_selector.py``); the only
    serializer allowed to render it is the owner's own bank endpoint.

    Frozen state lives on the parent question only — a choice is frozen iff
    its question is, so the state cannot drift between parent and children.
    Choices of an unfrozen question are freely replaced as a collection
    (nothing references them yet: attempt selections only ever point at
    choices of frozen questions, because freezing happens before the first
    answer row is created).

    ``ordering`` is by ``position`` then ``id`` and must never involve
    ``is_correct`` — a correct-first sort order would leak the key through
    row order.
    """

    question = models.ForeignKey(
        "questions.Question",
        on_delete=models.CASCADE,
        related_name="choices",
    )
    text = models.CharField(max_length=CHOICE_TEXT_MAX_LENGTH)
    is_correct = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "answer choice"
        verbose_name_plural = "answer choices"
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=["question", "position"], name="questions_choice_idx"),
        ]

    def __str__(self) -> str:
        """Return a truncated choice text."""
        return self.text[:60]
