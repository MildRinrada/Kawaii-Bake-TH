"""Per-course learner state."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel


class CourseProgress(TimeStampedModel):
    """One user's completion state for one course.

    Deliberately carries **no counters**  completed/total lesson counts are
    aggregated from ``LessonProgress`` at read time, so this row can never
    disagree with the rows it summarizes. What it stores is the one thing
    aggregation cannot recover: ``completed_at``, the moment the learner
    first finished every required lesson  stamped once, never cleared
    (lessons added later never un-complete a course; certificates will
    reference this).

    The row is created lazily on first progress activity in a course.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_progress",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="progress_records",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "course progress"
        verbose_name_plural = "course progress"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "course"), name="progress_course_unique"
            ),
        ]

    def __str__(self) -> str:
        """Return a readable label."""
        return f"CourseProgress<user={self.user_id} course={self.course_id}>"
