"""Per-lesson learner state."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel


class LessonProgress(TimeStampedModel):
    """One user's progress through one lesson.

    Owned by the progress domain since Phase 6 (previously in ``lessons`` 
    ADR 0012). Completion is a **timestamp, not a boolean**:

    * ``completed_at`` NULL = not completed; NOT NULL = completed. One field
      is both the flag and the "when".
    * ``first_completed_at`` is stamped once and survives un-completing 
      the durable history XP and certificates will reference (the
      ``published_at`` pattern).
    * ``last_viewed_at`` is the future watch-position/resume hook; written
      alongside completion changes in Phase 6.

    Rows are never deleted by unenrollment  a re-enrolling student owns
    their history.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        "lessons.Lesson",
        on_delete=models.CASCADE,
        related_name="progress_records",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    first_completed_at = models.DateTimeField(null=True, blank=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "lesson progress"
        verbose_name_plural = "lesson progress"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "lesson"), name="progress_lesson_unique"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "completed_at"], name="progress_lesson_idx"),
        ]

    def __str__(self) -> str:
        """Return a readable label."""
        return f"LessonProgress<user={self.user_id} lesson={self.lesson_id}>"

    @property
    def completed(self) -> bool:
        """Whether the lesson is currently completed."""
        return self.completed_at is not None
