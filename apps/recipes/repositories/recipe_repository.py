"""Write-side database access for recipes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django.db import IntegrityError, transaction

from apps.recipes.constants import SLUG_COLLISION_ATTEMPTS
from apps.recipes.exceptions import SlugGenerationError
from apps.recipes.models import Recipe
from apps.recipes.utils import slug_with_suffix


def create_recipe(*, author_id: int, slug_base: str, **fields: Any) -> Recipe:
    """Create a recipe, resolving slug collisions optimistically.

    Collisions are handled by *attempting the insert* and catching the unique
    violation, rather than by checking ``exists()`` first. A check-then-insert
    loop races under concurrent requests and issues a query per attempt.

    Each attempt is wrapped in its own ``atomic`` block, which becomes a
    SAVEPOINT when the service has already opened a transaction. On PostgreSQL,
    catching ``IntegrityError`` inside a transaction *without* a savepoint
    leaves the connection unusable for every subsequent query  a production
    failure SQLite does not reproduce.

    Args:
        author_id: Primary key of the author.
        slug_base: Slug base derived from the title; may be empty.
        **fields: Remaining recipe field values.

    Returns:
        The created recipe.

    Raises:
        SlugGenerationError: If no free slug was found after several attempts.
    """
    candidate = slug_base or slug_with_suffix("")

    for _ in range(SLUG_COLLISION_ATTEMPTS):
        try:
            with transaction.atomic():
                return Recipe.objects.create(
                    author_id=author_id, slug=candidate, **fields
                )
        except IntegrityError:
            candidate = slug_with_suffix(slug_base)

    raise SlugGenerationError


def update_recipe(*, recipe: Recipe, changes: Mapping[str, Any]) -> Recipe:
    """Apply changes to a recipe in a single UPDATE.

    Args:
        recipe: The recipe to update.
        changes: Field name to new value.

    Returns:
        The updated recipe.
    """
    if not changes:
        return recipe

    for field, value in changes.items():
        setattr(recipe, field, value)
    recipe.save(update_fields=[*changes.keys(), "updated_at"])
    return recipe


def set_categories(*, recipe: Recipe, category_ids: Sequence[int]) -> None:
    """Replace a recipe's category assignments.

    Writes only the join table, which this app owns; it never writes a category
    row.

    Args:
        recipe: The recipe to update.
        category_ids: Primary keys of the categories to assign.
    """
    recipe.categories.set(category_ids)


def delete_recipe(*, recipe: Recipe) -> None:
    """Delete a recipe and its children.

    Args:
        recipe: The recipe to delete.
    """
    recipe.delete()
