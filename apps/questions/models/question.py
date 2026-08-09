"""The reusable question entity."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.questions.constants import (
    EXPLANATION_MAX_LENGTH,
    QUESTION_TEXT_MAX_LENGTH,
    QuestionDifficulty,
    QuestionType,
)


class Question(TimeStampedModel):
    """One reusable question in the bank.

    Questions are shared assets: many quizzes may reference the same row, and
    attempt history points at it directly. Two consequences shape this model:

    * **``author`` is ownership only.** The bank's one permitted use of the
      user relation is comparing ``author_id`` to the viewer — this app never
      joins into profiles, preferences or any user state beyond identity.
    * **``frozen_at`` is the lifecycle state this app owns.** ``NULL`` means
      the question is editable and deletable; a timestamp means its content
      (text, type, choices) is permanently locked for historical integrity.
      A question knows *that* it is frozen, never *why* — callers with a
      reason (the quizzes app, at attempt start) push the state through
      ``question_service.freeze_questions()``. A timestamp rather than a
      boolean: same stamped-once pattern as ``published_at``/``completed_at``,
      and the audit trail is free.

    ``version`` and ``supersedes`` prepare versioning without implementing it:
    the future escape hatch for editing a frozen question is a **new row**
    (``version + 1``, ``supersedes`` pointing back) that quizzes upgrade to
    explicitly, leaving old attempts pointing at what was actually asked.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        db_index=True,
    )
    text = models.TextField(max_length=QUESTION_TEXT_MAX_LENGTH)
    explanation = models.TextField(
        max_length=EXPLANATION_MAX_LENGTH,
        blank=True,
        help_text=(
            "Shown to the learner after submitting. A learning aid, not part "
            "of what is asked or graded — editable even when frozen."
        ),
    )
    difficulty = models.CharField(
        max_length=20,
        choices=QuestionDifficulty.choices,
        default=QuestionDifficulty.MEDIUM,
        db_index=True,
    )

    version = models.PositiveIntegerField(default=1)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="superseded_by",
        null=True,
        blank=True,
        help_text="The earlier version this question replaces, if any.",
    )
    frozen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Stamped once when the question is first answered in an attempt; "
            "never cleared. Content is immutable from then on."
        ),
    )

    tags = models.ManyToManyField(
        "questions.QuestionTag",
        related_name="questions",
        blank=True,
    )

    class Meta:
        verbose_name = "question"
        verbose_name_plural = "questions"
        ordering = ("-id",)
        indexes = [
            models.Index(
                fields=["author", "question_type"], name="questions_author_type_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return a truncated question text."""
        return self.text[:60]

    @property
    def is_frozen(self) -> bool:
        """Whether the question's content is locked for historical integrity."""
        return self.frozen_at is not None
