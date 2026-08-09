"""Business logic for ingredient lines.

Ingredients are normally written as part of a recipe create or update. These
functions exist so the collection can also be replaced on its own — by a future
dedicated endpoint, an import command, or the AI ingredient assistant — without
that caller reaching into the repository.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.db import transaction

from apps.recipes.exceptions import RecipeNotVisibleError
from apps.recipes.models import RecipeIngredient
from apps.recipes.permissions.recipe_permissions import can_edit_recipe
from apps.recipes.repositories import ingredient_repository
from apps.recipes.selectors import recipe_selector
from apps.recipes.validators import ingredient_validator


def replace_ingredients(
    *,
    slug: str,
    viewer_id: int,
    viewer_is_staff: bool = False,
    lines: Sequence[dict[str, Any]],
) -> list[RecipeIngredient]:
    """Replace a recipe's ingredient lines wholesale.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        lines: Ingredient lines in display order.

    Returns:
        The stored lines.

    Raises:
        RecipeNotVisibleError: If absent or not the caller's to edit.
        django.core.exceptions.ValidationError: If a line is invalid.
    """
    recipe = recipe_selector.get_editable_recipe(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe is None or not can_edit_recipe(
        author_id=recipe.author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise RecipeNotVisibleError

    ingredient_validator.validate_lines(list(lines))

    with transaction.atomic():
        return ingredient_repository.replace_ingredients(
            recipe=recipe, lines=list(lines)
        )
