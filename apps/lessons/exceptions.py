"""Domain exceptions for the lessons app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class LessonNotVisibleError(DomainError):
    """Raised when a lesson does not exist for this viewer.

    Covers: unknown id, lesson on a course the viewer may not see, and an
    unpublished lesson seen by a non-owner. 404 in every case  the
    enumeration-protection layer, identical to Phase 2.
    """

    code = "not_found"
    status_code = 404
    message = "Lesson not found."


class EnrollmentRequiredError(DomainError):
    """Raised when lesson **content** is requested without enrollment.

    Deliberately 403, not 404  the one principled carve-out from the Phase 2
    rule. The syllabus already makes this lesson's existence public, so a 404
    would be a lie, and the frontend needs this exact signal to render the
    "Enroll" call-to-action. Only reachable *after* the 404 visibility layer
    has passed, so it never confirms anything hidden.
    """

    code = "enrollment_required"
    status_code = 403
    message = "Enroll in this course to access the lesson."


class CourseNotVisibleError(DomainError):
    """Raised when the course addressed by a lesson operation is not visible.

    This app's own error  a callee (courses) never raises for its caller
    (ADR 0008/0009).
    """

    code = "not_found"
    status_code = 404
    message = "Course not found."


class InvalidLessonRecipeError(DomainError):
    """Raised when linking a recipe the author cannot see."""

    code = "invalid_recipe"
    status_code = 400
    message = "The referenced recipe does not exist or is not visible to you."


class InvalidLessonQuizError(DomainError):
    """Raised when linking a quiz the author cannot see."""

    code = "invalid_quiz"
    status_code = 400
    message = "The referenced quiz does not exist or is not visible to you."


class LessonLimitExceededError(DomainError):
    """Raised when a course already has the maximum number of lessons."""

    code = "limit_exceeded"
    status_code = 400
    message = "This course already has the maximum number of lessons."


class InvalidReorderError(DomainError):
    """Raised when a reorder payload is not exactly the course's lesson set."""

    code = "invalid_reorder"
    status_code = 400
    message = (
        "The reorder list must contain every lesson of this course exactly once."
    )
