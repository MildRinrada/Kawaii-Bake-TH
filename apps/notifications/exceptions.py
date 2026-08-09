"""Domain exceptions for the notifications app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class NotificationNotFoundError(DomainError):
    """Raised when a notification is absent or not the caller's.

    "Not yours" and "does not exist" are the same 404 — ownership is
    enforced by the selector, so no endpoint can address another user's
    notification.
    """

    code = "not_found"
    status_code = 404
    message = "Notification not found."
