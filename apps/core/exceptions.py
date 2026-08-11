"""Framework-free domain exception base.

Services raise these. They carry their own error code and HTTP status so the
API layer can translate them declaratively  no ``try``/``except`` in views and
no registry to keep in sync. This module must never import DRF or Django HTTP:
services depend on it, and services stay transport-agnostic.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for business-rule failures.

    Attributes:
        code: Stable machine-readable identifier the frontend switches on.
        status_code: HTTP status the API layer should respond with.
        message: Human-readable, display-safe description.
    """

    code: str = "error"
    status_code: int = 400
    message: str = "Something went wrong."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialise the error.

        Args:
            message: Overrides the class-level message when supplied.
            details: Optional field-level context, shaped ``{field: [messages]}``.
        """
        self.message = message or self.message
        self.details: dict[str, Any] = details or {}
        super().__init__(self.message)


class RateLimitedError(DomainError):
    """Raised when a caller exceeds an endpoint's attempt allowance."""

    code = "rate_limited"
    status_code = 429
    message = "Too many attempts. Please try again later."
