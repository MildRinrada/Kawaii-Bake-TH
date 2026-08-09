"""Write-side database access for nutrition figures."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.recipes.models import Nutrition, Recipe


def upsert_nutrition(*, recipe: Recipe, values: Mapping[str, Any]) -> Nutrition:
    """Create or update a recipe's nutrition row.

    Created lazily on first write, so recipes without nutrition cost nothing.
    Race-safe because the table's primary key *is* the recipe.

    Args:
        recipe: The owning recipe.
        values: Nutrition field values.

    Returns:
        The stored nutrition row.
    """
    nutrition, _ = Nutrition.objects.get_or_create(recipe=recipe)
    if not values:
        return nutrition

    for field, value in values.items():
        setattr(nutrition, field, value)
    nutrition.save(update_fields=[*values.keys(), "updated_at"])
    return nutrition


def clear_nutrition(*, recipe: Recipe) -> None:
    """Remove a recipe's nutrition row.

    Args:
        recipe: The owning recipe.
    """
    Nutrition.objects.filter(recipe=recipe).delete()
