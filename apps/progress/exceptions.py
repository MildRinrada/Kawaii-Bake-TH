"""Domain exceptions for the progress app.

Its own copies of the boundary errors  a caller never raises a callee's
exception (ADR 0008), and the stable codes match the lessons app's so the
frontend branches identically.
"""

from __future__ import annotations

from apps.core.exceptions import DomainError


class ProgressLessonNotFoundError(DomainError):
    """Raised when the lesson does not exist for this viewer (404 layer)."""

    code = "not_found"
    status_code = 404
    message = "Lesson not found."


class ProgressCourseNotFoundError(DomainError):
    """Raised when the course is absent or hidden from the viewer."""

    code = "not_found"
    status_code = 404
    message = "Course not found."


class EnrollmentRequiredError(DomainError):
    """Raised when progress is touched without an access-granting enrollment.

    Same carve-out as lesson content (403 with a stable code, reachable only
    after the 404 layer): recording or reading progress is a course activity.
    """

    code = "enrollment_required"
    status_code = 403
    message = "Enroll in this course to track your progress."
