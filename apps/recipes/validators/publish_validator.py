"""Completeness rules that only apply when publishing.

Deliberately **not** enforced on every save. Requiring steps before a title can
be stored makes drafts useless and pushes unsaved state into the frontend  the
same orthogonality argument the users app makes for ``is_active`` versus
``is_email_verified``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.recipes.constants import TITLE_MIN_LENGTH
from apps.recipes.exceptions import RecipeNotPublishableError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.recipes.models import Recipe


def assert_publishable(recipe: Recipe) -> None:
    """Check that a recipe is complete enough to publish.

    Collects **every** failure rather than raising on the first one, so the
    frontend can render a publish checklist instead of making the author
    rediscover one problem per attempt.

    Args:
        recipe: The recipe about to be published. Its child collections are
            read, so the caller should pass a freshly loaded instance.

    Raises:
        RecipeNotPublishableError: If any requirement is unmet.
    """
    problems: dict[str, list[str]] = {}

    if len(recipe.title.strip()) < TITLE_MIN_LENGTH:
        problems["title"] = ["Add a longer title."]

    if not recipe.ingredients.exists():
        problems["ingredients"] = ["Add at least one ingredient."]

    if not recipe.steps.exists():
        problems["steps"] = ["Add at least one step."]

    if not recipe.categories.exists():
        problems["category_slugs"] = ["Choose at least one category."]

    if not recipe.cover_image:
        problems["cover_image"] = ["Add a cover image."]

    if problems:
        raise RecipeNotPublishableError(details=problems)
