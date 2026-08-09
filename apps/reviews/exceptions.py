"""Domain exceptions for the reviews app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class ReviewTargetNotFoundError(DomainError):
    """Raised when the reviewed recipe/course is absent or hidden.

    This app's own 404 — a callee (recipes, courses) never raises for its
    caller (ADR 0008).
    """

    code = "not_found"
    status_code = 404
    message = "Not found."


class ReviewNotFoundError(DomainError):
    """Raised when a review is absent, deleted, or not addressable by the viewer."""

    code = "not_found"
    status_code = 404
    message = "Review not found."


class AlreadyReviewedError(DomainError):
    """Raised on a second active review of the same target by the same user.

    Edit the existing review instead — one voice, one vote per target.
    """

    code = "already_reviewed"
    status_code = 409
    message = "You have already reviewed this. Edit your existing review instead."


class OwnContentReviewError(DomainError):
    """Raised when authors rate their own recipe or course.

    Self-reviews would let creators inflate the very averages future ranking
    and recommendation features will consume.
    """

    code = "own_content"
    status_code = 400
    message = "You cannot review your own content."


class ModerationNotAllowedError(DomainError):
    """Raised when a non-staff caller tries to change a review's status."""

    code = "permission_denied"
    status_code = 403
    message = "Only moderators can change a review's status."
