"""Domain exceptions for the certificates app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class CertificateCourseNotFoundError(DomainError):
    """Raised when the course is absent or hidden from the caller.

    This app's own 404 (ADR 0008) — courses never raises for its callers.
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
    stable code — the same signal the lesson content gate uses.
    """

    code = "enrollment_required"
    status_code = 403
    message = "Enroll in the course to request its certificate."


class CourseNotCompletedError(DomainError):
    """Raised when issuance is requested before every published lesson is done.

    409, not 400: the request is well-formed — it conflicts with the
    caller's current progress state (the submit-twice/`question_frozen`
    family).
    """

    code = "course_not_completed"
    status_code = 409
    message = "Complete every lesson in the course to earn its certificate."


class CertificateNumberExhaustedError(DomainError):
    """Raised when a unique certificate number cannot be allocated.

    Practically unreachable (five retries against a race window of one
    row); exists so the failure is explicit rather than an opaque 500.
    """

    code = "certificate_unavailable"
    status_code = 503
    message = "Certificate issuance is temporarily unavailable. Please try again."
