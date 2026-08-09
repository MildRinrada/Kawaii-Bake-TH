"""Write-side database access for enrollments."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.courses.constants import EnrollmentStatus
from apps.courses.models import Enrollment


def create_or_get(*, user_id: int, course_id: int) -> tuple[Enrollment, bool]:
    """Create an active enrollment, tolerating a concurrent duplicate.

    The unique constraint is the arbiter; a concurrent insert surfaces as
    ``IntegrityError`` inside a savepoint and resolves to a fetch.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        The enrollment and whether it was newly created.
    """
    try:
        with transaction.atomic():
            enrollment = Enrollment.objects.create(
                user_id=user_id,
                course_id=course_id,
                status=EnrollmentStatus.ACTIVE,
                enrolled_at=timezone.now(),
            )
            return enrollment, True
    except IntegrityError:
        return Enrollment.objects.get(user_id=user_id, course_id=course_id), False


def set_status(*, enrollment: Enrollment, status: str) -> Enrollment:
    """Change an enrollment's status.

    Args:
        enrollment: The enrollment to update.
        status: A value of :class:`EnrollmentStatus`.

    Returns:
        The updated enrollment.
    """
    enrollment.status = status
    enrollment.save(update_fields=["status", "updated_at"])
    return enrollment


def mark_completed(*, enrollment: Enrollment) -> Enrollment:
    """Record course completion.

    ``completed_at`` is stamped exactly once and never cleared — the durable
    fact a future certificate will reference.

    Args:
        enrollment: The enrollment to complete.

    Returns:
        The updated enrollment.
    """
    changes = ["status", "updated_at"]
    enrollment.status = EnrollmentStatus.COMPLETED
    if enrollment.completed_at is None:
        enrollment.completed_at = timezone.now()
        changes.append("completed_at")
    enrollment.save(update_fields=changes)
    return enrollment
