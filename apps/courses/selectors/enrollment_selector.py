"""Read-side queries for enrollments.

:class:`EnrollmentRef` and :func:`get_enrollment` are part of the public
cross-app API — the ``lessons`` app gates content and merges progress through
them without touching this app's models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db.models import QuerySet

from apps.courses.constants import EnrollmentStatus
from apps.courses.models import Enrollment


@dataclass(frozen=True)
class EnrollmentRef:
    """One user's enrollment state, safe to hand across the app boundary."""

    status: str
    enrolled_at: datetime
    completed_at: datetime | None

    @property
    def grants_access(self) -> bool:
        """Whether this enrollment unlocks course content."""
        return self.status in (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)


def get_enrollment(*, user_id: int, course_id: int) -> EnrollmentRef | None:
    """Fetch one user's enrollment in one course.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        An :class:`EnrollmentRef`, or ``None`` when never enrolled.
    """
    row = (
        Enrollment.objects.filter(user_id=user_id, course_id=course_id)
        .values("status", "enrolled_at", "completed_at")
        .first()
    )
    return EnrollmentRef(**row) if row else None


def get_enrollment_row(*, user_id: int, course_id: int) -> Enrollment | None:
    """Fetch the enrollment model row — internal to this app.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        The enrollment, or ``None``.
    """
    return Enrollment.objects.filter(user_id=user_id, course_id=course_id).first()


def list_enrolled_course_ids(*, user_id: int) -> QuerySet:
    """Course ids the user is actively enrolled in or has completed.

    Args:
        user_id: Primary key of the user.

    Returns:
        A values queryset of course ids.
    """
    return Enrollment.objects.filter(
        user_id=user_id,
        status__in=(EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED),
    ).values_list("course_id", flat=True)
