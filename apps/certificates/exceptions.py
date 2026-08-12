"""Domain exceptions for the certificates app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class CertificateCourseNotFoundError(DomainError):
    """Raised when the course is absent or hidden from the caller.

    This app's own 404 (ADR 0008)  courses never raises for its callers.
    """

    code = "not_found"
    status_code = 404
    message = "Not found."


class CertificateNotFoundError(DomainError):
    """Raised when a certificate/verification token matches nothing."""

    code = "not_found"
    status_code = 404
    message = "Certificate not found."


class CertificateEnrollmentRequiredError(DomainError):
    """Raised when the caller is not an active/completed student of the course.

    The course is visible (the 404 layer passed), so 403 with the standard
    stable code  the same signal the lesson content gate uses.
    """

    code = "enrollment_required"
    status_code = 403
    message = "Enroll in the course to request its certificate."


class CourseNotCompletedError(DomainError):
    """Raised when issuance is requested before every published lesson is done.

    409, not 400: the request is well-formed  it conflicts with the
    caller's current progress state (the submit-twice/`question_frozen`
    family).
    """

    code = "course_not_completed"
    status_code = 409
    message = "Complete every lesson in the course to earn its certificate."


class LegalNameRequiredError(DomainError):
    """Raised when the account has no legal name to print.

    409, not 400: the request is well-formed. Sign-up deliberately does
    not collect a legal name, so this is the state the *first* issuance
    of an account is expected to hit  the client answers it by asking
    the learner for their name and repeating the request with it. A
    certificate naming a handle is not a credential, so falling back to
    the username is not an option.
    """

    code = "legal_name_required"
    status_code = 409
    message = "Provide the name to print on the certificate."


class CertificateAlreadyRevokedError(DomainError):
    """Raised when revoking a certificate that is already revoked.

    409, not 200: silently confirming a second revocation would let two
    operators each believe *their* reason is the recorded one.
    """

    code = "certificate_already_revoked"
    status_code = 409
    message = "This certificate has already been revoked."


class BadgeNotFoundError(DomainError):
    """Raised when a badge definition cannot be located."""

    code = "badge_not_found"
    status_code = 404
    message = "Badge not found."


class DuplicateBadgeSlugError(DomainError):
    """Raised when a create or rename collides with an existing badge slug."""

    code = "duplicate_badge_slug"
    status_code = 409
    message = "A badge with this slug already exists."


class BadgeInUseError(DomainError):
    """Raised when deleting a badge that awarded achievements still reference.

    The FK is PROTECT by design - an earned fact must keep its
    presentation. Deactivating the badge is the supported way to retire it.
    """

    code = "badge_in_use"
    status_code = 409
    message = (
        "This badge has been awarded and cannot be deleted. "
        "Deactivate it instead."
    )


class CertificateNumberExhaustedError(DomainError):
    """Raised when a unique certificate number cannot be allocated.

    Practically unreachable (five retries against a race window of one
    row); exists so the failure is explicit rather than an opaque 500.
    """

    code = "certificate_unavailable"
    status_code = 503
    message = "Certificate issuance is temporarily unavailable. Please try again."
