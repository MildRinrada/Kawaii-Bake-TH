"""Read-side queries for enrollments.

:class:`EnrollmentRef` and :func:`get_enrollment` are part of the public
cross-app API  the ``lessons`` app gates content and merges progress through
them without touching this app's models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Q, QuerySet

from apps.courses.constants import CourseStatus, EnrollmentStatus
from apps.courses.models import Course, Enrollment


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
    """Fetch the enrollment model row  internal to this app.

    Args:
        user_id: Primary key of the user.
        course_id: Primary key of the course.

    Returns:
        The enrollment, or ``None``.
    """
    return Enrollment.objects.filter(user_id=user_id, course_id=course_id).first()


def list_enrollments_for_course(
    *, course_id: int, enrollment_status: str = "", search: str = ""
) -> QuerySet[Enrollment]:
    """Every learner of one course, newest enrollment first.

    Part of the public cross-app API for the ``IsAdminUser``-gated
    progress roster - the only caller allowed to see enrollments across
    users, which is why the profile join is acceptable here and nowhere
    else in this module.

    Args:
        course_id: Primary key of the course.
        enrollment_status: Optional :class:`EnrollmentStatus` narrowing.
        search: Matches the learner's username or display name.

    Returns:
        A lazy queryset with the user and profile preloaded.
    """
    queryset = Enrollment.objects.filter(course_id=course_id).select_related(
        "user__profile"
    )
    if enrollment_status:
        queryset = queryset.filter(status=enrollment_status)

    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(user__username__icontains=cleaned)
            | Q(user__profile__display_name__icontains=cleaned)
        )
    return queryset.order_by("-enrolled_at", "-id")


def list_course_enrollment_stats(*, search: str = "") -> QuerySet[Course]:
    """Published-or-archived courses annotated with enrollment counts.

    Draft courses are excluded: a course nobody could ever enroll in is
    noise on an operations dashboard. Counts aggregate this app's own
    ``enrollments`` reverse accessor - the no-stored-counters rule.

    Args:
        search: Matches the course title.

    Returns:
        Courses annotated with ``enrolled_count``, ``active_count``,
        ``completed_count`` and ``dropped_count``, most enrolled first.
    """
    queryset = Course.objects.exclude(status=CourseStatus.DRAFT)
    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(title__icontains=cleaned)

    return queryset.annotate(
        enrolled_count=Count("enrollments", distinct=True),
        active_count=Count(
            "enrollments",
            filter=Q(enrollments__status=EnrollmentStatus.ACTIVE),
            distinct=True,
        ),
        completed_count=Count(
            "enrollments",
            filter=Q(enrollments__status=EnrollmentStatus.COMPLETED),
            distinct=True,
        ),
        dropped_count=Count(
            "enrollments",
            filter=Q(enrollments__status=EnrollmentStatus.DROPPED),
            distinct=True,
        ),
    ).order_by("-enrolled_count", "-id")


def platform_enrollment_counts() -> dict[str, int]:
    """Headline enrollment totals for the staff dashboard.

    Returns:
        Mapping with ``total``, one key per :class:`EnrollmentStatus`
        value, and ``learners`` (distinct users who ever enrolled).
    """
    by_status = dict(
        Enrollment.objects.values_list("status").annotate(total=Count("id"))
    )
    return {
        "total": sum(by_status.values()),
        **{status: by_status.get(status, 0) for status in EnrollmentStatus.values},
        "learners": Enrollment.objects.values("user_id").distinct().count(),
    }


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


def enrolled_user_ids(*, course_id: int) -> list[int]:
    """User ids enrolled in (or graduated from) one course.

    Part of the cross-app audience API (ADR 0030): campaign targeting
    reaches enrollment data only through this selector. Dropped students
    chose to leave, so they are not part of the course's audience.

    Args:
        course_id: Primary key of the course.

    Returns:
        The enrolled or completed user ids.
    """
    return list(
        Enrollment.objects.filter(
            course_id=course_id,
            status__in=(EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED),
        ).values_list("user_id", flat=True)
    )


def completed_user_ids(*, course_id: int) -> list[int]:
    """User ids that completed one course (ADR 0030 audience API).

    Args:
        course_id: Primary key of the course.

    Returns:
        The completed user ids.
    """
    return list(
        Enrollment.objects.filter(
            course_id=course_id, status=EnrollmentStatus.COMPLETED
        ).values_list("user_id", flat=True)
    )
