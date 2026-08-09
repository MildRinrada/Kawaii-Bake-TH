"""Course enrollment."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.courses.constants import EnrollmentStatus


class Enrollment(TimeStampedModel):
    """One user's membership of one course.

    **One row per (user, course), forever.** A ``(user, course, status)`` key
    would permit duplicate active rows via a dropped intermediary and
    complicate every "is enrolled" check; state changes mutate this row.

    * ``enrolled_at`` records the *first* enrollment and is never re-stamped.
    * ``completed_at`` is stamped once and never cleared — the ``published_at``
      pattern. It is the durable fact a future certificate will reference, and
      it is what lets a re-enrolling user come back as ``COMPLETED`` rather
      than starting from zero.
    * Dropping is soft: nothing is deleted, and the user's lesson progress
      (owned by the ``lessons`` app) is untouched.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
        db_index=True,
    )
    enrolled_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "enrollment"
        verbose_name_plural = "enrollments"
        ordering = ("-enrolled_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "course"), name="courses_enrollment_unique"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="courses_enroll_user_idx"),
        ]

    def __str__(self) -> str:
        """Return a readable label."""
        return f"Enrollment<user={self.user_id} course={self.course_id}>"

    @property
    def is_active_or_completed(self) -> bool:
        """Whether this enrollment grants access to course content."""
        return self.status in (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)
