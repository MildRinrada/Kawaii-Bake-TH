"""The quiz aggregate root."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models.base import TimeStampedModel
from apps.quizzes.constants import (
    DEFAULT_PASS_PERCENT,
    QUIZ_SLUG_MAX_LENGTH,
    QUIZ_TITLE_MAX_LENGTH,
    QuizStatus,
    QuizVisibility,
)


class Quiz(TimeStampedModel):
    """A published set of references into the question bank.

    A quiz owns its *composition* (which questions, in what order, worth how
    many points  the ``QuizQuestion`` rows) but never the questions
    themselves. ``status`` and ``visibility`` are orthogonal and
    ``published_at`` is separate from ``status``, exactly as on Recipe and
    Course. Unlike Course there is no cross-app counter: the publish gate
    counts ``quiz_questions``, this app's own table.

    Reverse accessor reserved by the lessons app: ``lessons`` (its optional
    per-lesson quiz FK).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )

    title = models.CharField(max_length=QUIZ_TITLE_MAX_LENGTH)
    slug = models.SlugField(
        max_length=QUIZ_SLUG_MAX_LENGTH,
        unique=True,
        allow_unicode=True,
        help_text="Frozen once the quiz is first published.",
    )
    description = models.TextField(blank=True)
    pass_percent = models.PositiveSmallIntegerField(
        default=DEFAULT_PASS_PERCENT,
        help_text="Minimum percentage that counts as passing.",
    )

    status = models.CharField(
        max_length=20,
        choices=QuizStatus.choices,
        default=QuizStatus.DRAFT,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=20,
        choices=QuizVisibility.choices,
        default=QuizVisibility.PUBLIC,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "quiz"
        verbose_name_plural = "quizzes"
        ordering = ("-published_at", "-created_at", "-id")
        constraints = [
            models.UniqueConstraint(Lower("slug"), name="quizzes_quiz_slug_ci_unique"),
            models.CheckConstraint(
                condition=Q(pass_percent__lte=100),
                name="quizzes_pass_percent_max_100",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "visibility", "-published_at"],
                name="quizzes_listing_idx",
            ),
            models.Index(fields=["owner", "status"], name="quizzes_owner_idx"),
        ]

    def __str__(self) -> str:
        """Return the quiz title."""
        return self.title

    @property
    def is_published(self) -> bool:
        """Whether the quiz is currently published."""
        return self.status == QuizStatus.PUBLISHED

    @property
    def slug_is_frozen(self) -> bool:
        """Whether the slug may no longer change."""
        return self.published_at is not None
