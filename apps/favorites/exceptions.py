"""Domain exceptions for the favorites app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class FavoriteTargetNotFoundError(DomainError):
    """Raised when the favorited recipe/course is absent or hidden.

    This app's own 404 — hidden content cannot be favorited, and unfavoriting
    something that has since gone private fails closed the same way.
    """

    code = "not_found"
    status_code = 404
    message = "Not found."
