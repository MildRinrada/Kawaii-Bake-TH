"""Domain exceptions for the recommendation app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class RecipeNotFoundError(DomainError):
    """Raised when the recipe being asked about is absent or hidden.

    This app's own 404 (ADR 0008)  hidden and absent are indistinguishable
    to the client, exactly as on the recipes endpoints themselves.
    """

    code = "not_found"
    status_code = 404
    message = "Recipe not found."
