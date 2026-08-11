"""The per-question snapshot rows of an attempt."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel


class QuizAttemptAnswer(TimeStampedModel):
    """One question inside one attempt.

    Rows are created **empty at attempt start**  that is the composition
    snapshot. Position and ``points_possible`` are copied from the
    ``QuizQuestion`` rows at that moment, and grading later reads only this
    snapshot plus the (frozen) bank questions. An instructor replacing the
    quiz's composition mid-attempt therefore cannot change what this attempt
    is graded against. Creating the rows at start is also the prepared seam
    for randomized ordering (shuffle at insert) and timed quizzes.

    ``question`` is ``PROTECT``: attempt history pins bank questions forever.
    ``selected_choices`` has no ``PROTECT`` (M2M cannot), but the invariant
    holds structurally: selections only ever reference choices of **frozen**
    questions  freezing happens in the same transaction that creates these
    rows, before any selection exists, and frozen choices cannot be deleted.

    ``was_correct`` is three-valued: ``NULL`` until graded.
    """

    attempt = models.ForeignKey(
        "quizzes.QuizAttempt",
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        "questions.Question",
        on_delete=models.PROTECT,
        related_name="attempt_answers",
    )
    position = models.PositiveSmallIntegerField(default=0)
    points_possible = models.PositiveSmallIntegerField(default=0)

    selected_choices = models.ManyToManyField(
        "questions.AnswerChoice",
        related_name="attempt_selections",
        blank=True,
    )
    was_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "quiz attempt answer"
        verbose_name_plural = "quiz attempt answers"
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "question"), name="quizzes_unique_attempt_answer"
            ),
        ]

    def __str__(self) -> str:
        """Return the answer description."""
        return f"attempt {self.attempt_id} · question {self.question_id}"
