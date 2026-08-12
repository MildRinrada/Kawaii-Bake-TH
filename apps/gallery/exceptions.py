"""Domain exceptions for the gallery app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class GalleryPostNotFoundError(DomainError):
    """Raised when a post is absent, or hidden from this viewer.

    Unpublished-and-not-yours and nonexistent are the same 404  the
    fail-closed rule every domain follows.
    """

    code = "not_found"
    status_code = 404
    message = "Gallery post not found."


class InvalidGalleryReferenceError(DomainError):
    """Raised when the referenced recipe/course is not publicly visible.

    A gallery post is public by default, so its reference must be content
    the public could open  otherwise the post's card would leak a hidden
    title.
    """

    code = "invalid_reference"
    status_code = 400
    message = "The referenced content does not exist or is not public."


class GalleryCommentNotFoundError(DomainError):
    """Raised when a comment is absent, or not the caller's to remove.

    Not-yours and nonexistent are again the same 404: a stranger must not
    learn that a comment id exists by the shape of the refusal.
    """

    code = "not_found"
    status_code = 404
    message = "Comment not found."


class InvalidImageOrderError(DomainError):
    """Raised when a reorder payload is not exactly the post's image set."""

    code = "invalid_order"
    status_code = 400
    message = "image_ids must contain exactly this post's image ids."
