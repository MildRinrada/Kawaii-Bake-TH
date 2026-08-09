"""Domain exceptions for the courses app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class CourseNotVisibleError(DomainError):
    """Raised when a course is absent, or present but hidden from the viewer.

    404 in both cases — a 403 would confirm the slug exists.
    """

    code = "not_found"
    status_code = 404
    message = "Course not found."


class CourseSlugImmutableError(DomainError):
    """Raised when changing the slug of an already-published course."""

    code = "slug_immutable"
    status_code = 409
    message = (
        "The URL of a published course cannot be changed, because existing "
        "links would break."
    )


class CourseSlugTakenError(DomainError):
    """Raised when a requested slug is already used by another course."""

    code = "slug_taken"
    status_code = 409
    message = "That URL is already in use by another course."


class CourseSlugGenerationError(DomainError):
    """Raised when a unique slug could not be generated."""

    code = "slug_generation_failed"
    status_code = 500
    message = "Could not generate a unique URL for this course. Please try again."


class CourseNotPublishableError(DomainError):
    """Raised when a course fails the completeness checks required to publish.

    Carries **every** failure in ``details`` so the frontend can render a
    publish checklist.
    """

    code = "course_not_publishable"
    status_code = 400
    message = "This course is not ready to publish."


class InvalidCourseCategoryError(DomainError):
    """Raised when assigning categories that do not exist or are inactive."""

    code = "invalid_category"
    status_code = 400
    message = "One or more categories are not valid."


class OwnCourseEnrollmentError(DomainError):
    """Raised when an instructor tries to enroll in their own course."""

    code = "own_course"
    status_code = 400
    message = "You cannot enroll in your own course."


class CourseNotEnrollableError(DomainError):
    """Raised when enrolling in a course that is not open for enrollment."""

    code = "not_enrollable"
    status_code = 400
    message = "This course is not open for enrollment."


class NotEnrolledError(DomainError):
    """Raised when unenrolling from a course the user was never enrolled in."""

    code = "not_enrolled"
    status_code = 404
    message = "You are not enrolled in this course."
