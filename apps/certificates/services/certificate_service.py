"""Business logic for certificate issuance, revocation and verification.

The one rule everything here bends around: **progress owns completion**.
This service reads the stamped completion fact through progress' public
selector and never counts a lesson itself.
"""

from __future__ import annotations

import logging
import uuid

from django.db import IntegrityError

from apps.certificates.exceptions import (
    CertificateCourseNotFoundError,
    CertificateEnrollmentRequiredError,
    CertificateNotFoundError,
    CourseNotCompletedError,
)
from apps.certificates.models import Certificate
from apps.certificates.repositories import certificate_repository
from apps.certificates.selectors import certificate_selector
from apps.certificates.services import achievement_service
from apps.courses.selectors import course_selector, enrollment_selector
from apps.progress.selectors import progress_selector
from apps.users.selectors import user_selector

logger = logging.getLogger("kawaiibake.certificates")


def _printable_name(student) -> str:  # noqa: ANN001 - apps.users.models.User
    """The name a certificate should print: the real name, not the handle.

    Falls back to the username only when no display name was ever set —
    the same rule ``AuthorRefSerializer`` uses everywhere else a name is
    shown. This is a one-time snapshot taken at issuance
    (``Certificate.student_name`` never changes afterward, see the model
    docstring); a learner renaming their profile later does not retitle
    certificates already printed, the same way a paper certificate would
    not rewrite itself.

    Args:
        student: The issuing user, or ``None``.

    Returns:
        The name to print, or ``""`` if there is no student.
    """
    if student is None:
        return ""
    profile = getattr(student, "profile", None)
    return (profile.display_name if profile else "") or student.username


def issue_if_completed(
    *, user_id: int, course_slug: str, viewer_is_staff: bool = False
) -> tuple[Certificate, bool]:
    """Issue the caller's certificate for a completed course, idempotently.

    The gate order mirrors the lesson content gate: existence (404) →
    membership (403) → state (409). Completion is **trusted** from
    progress — ``CourseProgress.completed_at``, stamped once by
    ``recalculate_course_progress`` — never recomputed here.

    Args:
        user_id: Primary key of the caller.
        course_slug: Slug of the course.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The certificate and whether this call created it (existing → False).

    Raises:
        CertificateCourseNotFoundError: If the course is absent or hidden.
        CertificateEnrollmentRequiredError: If the caller is not a student.
        CourseNotCompletedError: If progress has not recorded completion.
    """
    course = course_selector.get_course_ref(
        slug=course_slug, viewer_id=user_id, viewer_is_staff=viewer_is_staff
    )
    if course is None:
        raise CertificateCourseNotFoundError

    enrollment = enrollment_selector.get_enrollment(
        user_id=user_id, course_id=course.id
    )
    if enrollment is None or not enrollment.grants_access:
        raise CertificateEnrollmentRequiredError

    completed_at = progress_selector.get_course_completed_at(
        user_id=user_id, course_id=course.id
    )
    if completed_at is None:
        raise CourseNotCompletedError

    existing = certificate_selector.get_active_certificate(
        user_id=user_id, course_id=course.id
    )
    if existing is not None:
        return existing, False

    student = user_selector.get_by_id(user_id=user_id)
    try:
        certificate = certificate_repository.issue_certificate(
            user_id=user_id,
            course_id=course.id,
            student_name=_printable_name(student),
            course_title=course.title,
            completed_at=completed_at,
        )
    except IntegrityError:
        # Lost the (user, course) race — the winner's certificate is ours.
        certificate = certificate_selector.get_active_certificate(
            user_id=user_id, course_id=course.id
        )
        if certificate is None:  # pragma: no cover - revoked mid-race
            raise
        return certificate, False

    logger.info(
        "certificate_issued number=%s course_id=%s user=%s",
        certificate.certificate_number,
        course.id,
        user_id,
    )
    achievement_service.award_course_achievements(
        user_id=user_id, course_id=course.id, course_title=course.title
    )
    return certificate, True


def revoke(*, certificate_id: int, user_id: int) -> Certificate:
    """Revoke a certificate — stamp-once, everything else untouched.

    No HTTP endpoint exposes this in Phase 8; it exists for operators
    (tests, admin actions, future moderation). Addressed through the owner
    scope so a future endpoint inherits the 404-not-yours rule.

    Args:
        certificate_id: Primary key of the certificate.
        user_id: Primary key of the certificate's owner.

    Returns:
        The revoked certificate.

    Raises:
        CertificateNotFoundError: If absent or not the owner's.
    """
    certificate = certificate_selector.get_owned_certificate(
        certificate_id=certificate_id, user_id=user_id
    )
    if certificate is None:
        raise CertificateNotFoundError
    certificate_repository.revoke(certificate=certificate)
    certificate.refresh_from_db()
    logger.info(
        "certificate_revoked number=%s user=%s",
        certificate.certificate_number,
        user_id,
    )
    return certificate


def verify_token(*, token: uuid.UUID) -> Certificate:
    """Resolve a public verification token.

    Returns revoked certificates too — "revoked" is a verification answer,
    not a missing record. Unknown tokens are 404.

    Args:
        token: The UUID from the verification URL.

    Returns:
        The certificate.

    Raises:
        CertificateNotFoundError: If the token matches nothing.
    """
    certificate = certificate_selector.get_by_verification_token(token=token)
    if certificate is None:
        raise CertificateNotFoundError
    return certificate
