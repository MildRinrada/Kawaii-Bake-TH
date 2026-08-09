"""One user's attempt at one quiz."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models.base import TimeStampedModel
from apps.quizzes.constants import AttemptStatus


class QuizAttempt(TimeStampedModel):
    """One graded (or in-progress) run through a quiz.

    Attempt history is permanent: ``quiz`` is ``PROTECT`` (delete the quiz →
    409, archive instead) and every result figure is **denormalized onto this
    row at grading time**. Deliberate: history must not change when a question
    is edited or a quiz recomposed later, so nothing here is ever recomputed
    from live data. ``max_score`` is stamped at *start* (from the composition
    snapshot), not submit — grading never reads ``QuizQuestion`` again.

    The partial unique constraint allows exactly one open attempt per user per
    quiz while permitting unlimited submitted history — retry limits are a
    future count over these rows, no schema change.

    ``passed`` is three-valued: ``NULL`` until graded.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.PROTECT,
        related_name="attempts",
    )

    status = models.CharField(
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.IN_PROGRESS,
        db_index=True,
    )
    started_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)

    score = models.PositiveIntegerField(default=0)
    max_score = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    incorrect_count = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    passed = models.BooleanField(null=True, blank=True)

    class Meta:
        verbose_name = "quiz attempt"
        verbose_name_plural = "quiz attempts"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "quiz"),
                condition=Q(status="in_progress"),
                name="quizzes_one_open_attempt",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "quiz", "-id"], name="quizzes_attempt_idx"),
        ]

    def __str__(self) -> str:
        """Return the attempt description."""
        return f"attempt {self.pk} · quiz {self.quiz_id} · user {self.user_id}"

    @property
    def is_submitted(self) -> bool:
        """Whether this attempt has been graded."""
        return self.status == AttemptStatus.SUBMITTED
