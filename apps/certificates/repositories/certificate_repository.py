"""Write operations for certificates and achievements.

There is deliberately no generic update function: certificates are
immutable records, and the single permitted mutation  revocation  is a
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
from apps.certificates.models import (
    Achievement,
    BadgeDefinition,
    Certificate,
    CertificateTemplate,
)


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
    the caller's to handle  an ``IntegrityError`` still escaping this
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
            exists  the caller resolves it to the existing row.
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


def revoke(
    *, certificate: Certificate, actor_id: int | None = None, reason: str = ""
) -> bool:
    """Stamp ``revoked_at`` once. Idempotent; nothing else ever changes.

    Args:
        certificate: The certificate to revoke.
        actor_id: The staff member responsible, recorded with the stamp.
        reason: Why the credential was withdrawn.

    Returns:
        ``True`` if this call performed the revocation.
    """
    updated = Certificate.objects.filter(
        pk=certificate.pk, revoked_at__isnull=True
    ).update(
        revoked_at=timezone.now(), revoked_by_id=actor_id, revoked_reason=reason
    )
    return bool(updated)


def award_achievement(
    *,
    user_id: int,
    achievement_type: str,
    metadata: dict | None = None,
) -> tuple[Achievement, bool]:
    """Record an achievement fact, idempotently.

    ``get_or_create`` against the (user, type) unique: the first call
    earns, every later call returns the original row untouched  awarded_at
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


def get_or_create_template(
    *, course_id: int, default_design: dict
) -> CertificateTemplate:
    """Fetch a course's template row, creating it from the default design.

    Args:
        course_id: Primary key of the course.
        default_design: Seed draft when no row exists yet.

    Returns:
        The template row.
    """
    template, _ = CertificateTemplate.objects.get_or_create(
        course_id=course_id, defaults={"draft_design": default_design}
    )
    return template


def save_draft(
    *, template: CertificateTemplate, design: dict, actor_id: int
) -> CertificateTemplate:
    """Replace the draft design (the autosave write).

    Args:
        template: The template row.
        design: The validated design document.
        actor_id: The staff member editing.

    Returns:
        The updated template.
    """
    template.draft_design = design
    template.updated_by_id = actor_id
    template.save(update_fields=["draft_design", "updated_by", "updated_at"])
    return template


def publish_template(
    *, template: CertificateTemplate, actor_id: int
) -> CertificateTemplate:
    """Freeze the current draft as the published design.

    Args:
        template: The template row.
        actor_id: The staff member publishing.

    Returns:
        The updated template.
    """
    template.published_design = template.draft_design
    template.published_at = timezone.now()
    template.updated_by_id = actor_id
    template.save(
        update_fields=[
            "published_design",
            "published_at",
            "updated_by",
            "updated_at",
        ]
    )
    return template


def delete_template(*, template: CertificateTemplate) -> None:
    """Remove the row entirely — the course falls back to the default.

    Args:
        template: The template to delete.
    """
    template.delete()
