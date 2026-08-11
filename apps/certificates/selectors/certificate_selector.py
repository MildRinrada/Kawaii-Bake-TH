"""Read-side queries for certificates and achievements.

Owner lists filter by user; the one public read is keyed **only** by the
unguessable verification token  certificate numbers are sequential and
must never become a lookup key.
"""

from __future__ import annotations

import uuid

from django.db.models import Q, QuerySet

from apps.certificates.models import Achievement, Certificate


def list_all_certificates(
    *, search: str = "", cert_status: str = "", username: str = ""
) -> QuerySet[Certificate]:
    """The platform-wide certificate registry, for staff only.

    Args:
        search: Matches the certificate number, the printed student name,
            the course title, or the holder's handle/display name.
        cert_status: ``valid`` or ``revoked``; empty means both.

    Returns:
        A lazy queryset for pagination, newest first, with the holder
        and the revoking operator preloaded.
    """
    queryset = Certificate.objects.select_related(
        "user__profile", "revoked_by"
    )

    if cert_status == "valid":
        queryset = queryset.filter(revoked_at__isnull=True)
    elif cert_status == "revoked":
        queryset = queryset.filter(revoked_at__isnull=False)

    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(certificate_number__icontains=cleaned)
            | Q(student_name__icontains=cleaned)
            | Q(course_title__icontains=cleaned)
            | Q(user__username__icontains=cleaned)
            | Q(user__profile__display_name__icontains=cleaned)
        )
    if username.strip():
        queryset = queryset.filter(user__username__iexact=username.strip())
    return queryset.order_by("-issued_at", "-id")


def get_by_id(*, certificate_id: int) -> Certificate | None:
    """Fetch one certificate by primary key - staff addressing only.

    Owner-facing reads keep going through :func:`get_owned_certificate`;
    the pk is never a public lookup key.

    Args:
        certificate_id: The certificate primary key.

    Returns:
        The certificate, or ``None``.
    """
    return (
        Certificate.objects.select_related("user__profile", "revoked_by")
        .filter(pk=certificate_id)
        .first()
    )


def get_active_certificate(
    *, user_id: int, course_id: int
) -> Certificate | None:
    """Fetch the user's active (non-revoked) certificate for a course.

    Args:
        user_id: Primary key of the student.
        course_id: Primary key of the course.

    Returns:
        The certificate, or ``None``.
    """
    return Certificate.objects.filter(
        user_id=user_id, course_id=course_id, revoked_at__isnull=True
    ).first()


def get_owned_certificate(
    *, certificate_id: int, user_id: int
) -> Certificate | None:
    """Fetch one certificate, restricted to its owner.

    Args:
        certificate_id: Primary key of the certificate.
        user_id: Primary key of the caller.

    Returns:
        The certificate, or ``None`` when absent or not the caller's.
    """
    return Certificate.objects.filter(pk=certificate_id, user_id=user_id).first()


def list_for_user(*, user_id: int) -> QuerySet[Certificate]:
    """The user's certificates, newest first  revoked ones included.

    No joins: the printable snapshot makes every list field local, so the
    listing costs one query regardless of length.

    Args:
        user_id: Primary key of the caller.

    Returns:
        A lazy queryset.
    """
    return Certificate.objects.filter(user_id=user_id)


def get_by_verification_token(*, token: uuid.UUID) -> Certificate | None:
    """Fetch a certificate by its public verification token.

    Args:
        token: The UUID from the verification URL.

    Returns:
        The certificate (valid or revoked), or ``None``.
    """
    return Certificate.objects.filter(verification_token=token).first()


def certified_course_count(*, user_id: int) -> int:
    """How many distinct courses the user has ever been certified for.

    Part of the public cross-app API (Phase 9)  the fact count behind
    certificate XP. Distinct courses, revoked included: the earning event
    happened, and a revoke-then-reissue must not count twice.

    Args:
        user_id: Primary key of the user.

    Returns:
        The distinct certified-course count.
    """
    return (
        Certificate.objects.filter(user_id=user_id, course__isnull=False)
        .values("course_id")
        .distinct()
        .count()
    )


def certified_course_ids(*, user_id: int) -> list[int]:
    """The distinct courses the user has ever been certified for.

    Part of the public cross-app API (Phase 13)  the identified sibling
    of :func:`certified_course_count`, same rule: distinct courses,
    revoked included, so a revoke-then-reissue cannot earn twice.

    Args:
        user_id: Primary key of the user.

    Returns:
        Course ids, ascending for determinism.
    """
    return list(
        Certificate.objects.filter(user_id=user_id, course__isnull=False)
        .order_by("course_id")
        .values_list("course_id", flat=True)
        .distinct()
    )


def list_achievements_for_user(*, user_id: int) -> QuerySet[Achievement]:
    """The user's achievements, newest first, badges preloaded.

    Args:
        user_id: Primary key of the caller.

    Returns:
        A lazy queryset with ``badge`` selected.
    """
    return Achievement.objects.filter(user_id=user_id).select_related("badge")


def earned_types(*, user_id: int) -> set[str]:
    """Which achievement types the user already holds.

    Args:
        user_id: Primary key of the user.

    Returns:
        The set of earned type values.
    """
    return set(
        Achievement.objects.filter(user_id=user_id).values_list(
            "achievement_type", flat=True
        )
    )
