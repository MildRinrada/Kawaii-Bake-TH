"""Domain exceptions for the recipes app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class RecipeNotVisibleError(DomainError):
    """Raised when a recipe is absent, or present but hidden from the viewer.

    Reported as 404 rather than 403 in both cases: a 403 would confirm that the
    slug exists, turning the endpoint into an enumeration oracle for private
    and draft recipes.
    """

    code = "not_found"
    status_code = 404
    message = "Recipe not found."


class SlugImmutableError(DomainError):
    """Raised when changing the slug of an already-published recipe."""

    code = "slug_immutable"
    status_code = 409
    message = (
        "The URL of a published recipe cannot be changed, because existing "
        "links would break."
    )


class SlugTakenError(DomainError):
    """Raised when a requested slug is already used by another recipe."""

    code = "slug_taken"
    status_code = 409
    message = "That URL is already in use by another recipe."


class InvalidCategoryError(DomainError):
    """Raised when assigning categories that do not exist or are inactive."""

    code = "invalid_category"
    status_code = 400
    message = "One or more categories are not valid."


class RecipeNotPublishableError(DomainError):
    """Raised when a recipe fails the completeness checks required to publish.

    Carries **every** failure at once in ``details`` so the frontend can render
    a publish checklist instead of surfacing one problem per attempt.
    """

    code = "recipe_not_publishable"
    status_code = 400
    message = "This recipe is not ready to publish."


class RecipeLimitExceededError(DomainError):
    """Raised when a collection on a recipe exceeds its permitted size."""

    code = "limit_exceeded"
    status_code = 400
    message = "Too many items."


class SlugGenerationError(DomainError):
    """Raised when a unique slug could not be generated after several attempts."""

    code = "slug_generation_failed"
    status_code = 500
    message = "Could not generate a unique URL for this recipe. Please try again."
