"""Write operations for certificates and achievements.

There is deliberately no generic update function: certificates are
immutable records, and the single permitted mutation — revocation — is a
stamp-once conditional UPDATE.
"""

from __future__ import annotations

from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.certificates.constants import (
    CERTIFICATE_NUMBER_PREFIX,
    CERTIFICATE_SEQUENCE_DIGITS,
    NUMBER_ALLOCATION_ATTEMPTS,
)
from apps.certificates.exceptions import CertificateNumberExhaustedError
from apps.certificates.models import Achievement, BadgeDefinition, Certificate


def _next_number(*, year: int) -> str:
    """Compute the next certificate number for a year.

    Reads the current maximum rather than counting rows, so revoked and
    re-issued certificates can never cause a collision by inflating a
    count. Zero-padding makes lexicographic max equal numeric max.
    """
    prefix = f"{CERTIFICATE_NUMBER_PREFIX}-{year}-"
    latest = (
        Certificate.objects.filter(certificate_number__startswith=prefix)
        .order_by("-certificate_number")
        .values_list("certificate_number", flat=True)
        .first()
    )
    sequence = int(latest.rsplit("-", 1)[1]) + 1 if latest else 1
    return f"{prefix}{sequence:0{CERTIFICATE_SEQUENCE_DIGITS}d}"


def issue_certificate(
    *,
    user_id: int,
    course_id: int,
    student_name: str,
    course_title: str,
    completed_at: datetime,
) -> Certificate:
    """Create a certificate with a freshly allocated number.

    Two issuances can race for the same sequence number; the global unique
    on ``certificate_number`` decides, and the loser recomputes inside a
    savepoint (the tag-creation pattern). The **(user, course)** race is
    the caller's to handle — an ``IntegrityError`` still escaping this
    function means "someone else just issued this exact certificate".

    Args:
        user_id: Primary key of the student.
        course_id: Primary key of the course.
        student_name: Snapshot of the student's public handle.
        course_title: Snapshot of the course title.
        completed_at: The completion fact read from progress.

    Returns:
        The saved certificate.

    Raises:
        CertificateNumberExhaustedError: If every allocation attempt lost
            its race (practically unreachable).
        IntegrityError: If an active certificate for (user, course) already
            exists — the caller resolves it to the existing row.
    """
    now = timezone.now()
    for _attempt in range(NUMBER_ALLOCATION_ATTEMPTS):
        number = _next_number(year=now.year)
        try:
            with transaction.atomic():
                return Certificate.objects.create(
                    user_id=user_id,
                    course_id=course_id,
                    certificate_number=number,
                    issued_at=now,
                    student_name=student_name,
                    course_title=course_title,
                    completed_at=completed_at,
                )
        except IntegrityError:
            # Number collision → retry with a recomputed sequence.
            # (User, course) collision → re-raise for the caller: retrying
            # cannot succeed, the certificate already exists.
            if Certificate.objects.filter(certificate_number=number).exists():
                continue
            raise
    raise CertificateNumberExhaustedError


def revoke(*, certificate: Certificate) -> bool:
    """Stamp ``revoked_at`` once. Idempotent; nothing else ever changes.

    Args:
        certificate: The certificate to revoke.

    Returns:
        ``True`` if this call performed the revocation.
    """
    updated = Certificate.objects.filter(
        pk=certificate.pk, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
    return bool(updated)


def award_achievement(
    *,
    user_id: int,
    achievement_type: str,
    metadata: dict | None = None,
) -> tuple[Achievement, bool]:
    """Record an achievement fact, idempotently.

    ``get_or_create`` against the (user, type) unique: the first call
    earns, every later call returns the original row untouched — awarded_at
    and metadata are never rewritten (append-only).

    Args:
        user_id: Primary key of the user.
        achievement_type: A value of :class:`AchievementType`.
        metadata: Context for the earning event (course id, counts).

    Returns:
        The achievement and whether this call created it.
    """
    badge = BadgeDefinition.objects.filter(
        slug=achievement_type, is_active=True
    ).first()
    return Achievement.objects.get_or_create(
        user_id=user_id,
        achievement_type=achievement_type,
        defaults={"badge": badge, "metadata": metadata or {}},
    )
