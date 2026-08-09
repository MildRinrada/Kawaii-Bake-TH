"""Normalisation and bounds for user-supplied assistant input.

The serializer is the transport gate; the service re-checks here because
services must not trust the transport (they are also called from tests,
commands and future internal callers).
"""

from __future__ import annotations

from apps.assistant.constants import MESSAGE_MAX_LENGTH
from apps.core.exceptions import DomainError


class InvalidMessageError(DomainError):
    """Raised when a message is empty or exceeds the length cap."""

    code = "invalid_message"
    status_code = 400
    message = "Message must be between 1 and 4000 characters."


def normalize_content(content: str) -> str:
    """Strip and bound a user message.

    Args:
        content: Raw message text.

    Returns:
        The stripped text.

    Raises:
        InvalidMessageError: If empty after stripping, or over the cap.
    """
    cleaned = (content or "").strip()
    if not cleaned or len(cleaned) > MESSAGE_MAX_LENGTH:
        raise InvalidMessageError
    return cleaned
