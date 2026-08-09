"""Domain exceptions for the recipe categories app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class CategoryNotFoundError(DomainError):
    """Raised when a category cannot be located."""

    code = "category_not_found"
    status_code = 404
    message = "Category not found."
