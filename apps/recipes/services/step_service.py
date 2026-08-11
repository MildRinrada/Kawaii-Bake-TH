"""Business logic for preparation steps.

As with ingredients, steps are normally written through a recipe create or
update. This module lets the collection be replaced independently without a
caller touching the repository directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.db import transaction

from apps.recipes.exceptions import RecipeNotVisibleError
from apps.recipes.models import RecipeStep
from apps.recipes.permissions.recipe_permissions import can_edit_recipe
from apps.recipes.repositories import step_repository
from apps.recipes.selectors import recipe_selector
from apps.recipes.validators import step_validator


def replace_steps(
    *,
    slug: str,
    viewer_id: int,
    viewer_is_staff: bool = False,
    steps: Sequence[dict[str, Any]],
) -> list[RecipeStep]:
    """Replace a recipe's steps wholesale.

    Reordering is expressed simply by submitting the array in a different
    order  ``position`` is always derived from the array, never from the client.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        steps: Steps in display order.

    Returns:
        The stored steps.

    Raises:
        RecipeNotVisibleError: If absent or not the caller's to edit.
        django.core.exceptions.ValidationError: If a step is invalid.
    """
    recipe = recipe_selector.get_editable_recipe(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe is None or not can_edit_recipe(
        author_id=recipe.author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise RecipeNotVisibleError

    step_validator.validate_steps(list(steps))

    with transaction.atomic():
        return step_repository.replace_steps(recipe=recipe, steps=list(steps))
