"""Nutrition handling  validation and storage only.

Phase 2 performs **no arithmetic** on nutrition: no summing over ingredients,
no unit conversion, no per-serving division. Values are author-supplied and are
echoed back verbatim. ``source`` is always ``manual``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.recipes.constants import NutritionSource
from apps.recipes.models import Nutrition, Recipe
from apps.recipes.repositories import nutrition_repository
from apps.recipes.validators.nutrition_validator import validate_nutrition


def set_nutrition(*, recipe: Recipe, values: Mapping[str, Any]) -> Nutrition:
    """Validate and store nutrition figures for a recipe.

    Args:
        recipe: The owning recipe.
        values: Submitted nutrition fields.

    Returns:
        The stored nutrition row.

    Raises:
        django.core.exceptions.ValidationError: If a figure is implausible.
    """
    validate_nutrition(values)

    stored = dict(values)
    # Phase 2 has no estimator, so anything written here came from a human.
    stored["source"] = NutritionSource.MANUAL
    return nutrition_repository.upsert_nutrition(recipe=recipe, values=stored)


def clear_nutrition(*, recipe: Recipe) -> None:
    """Remove a recipe's nutrition figures.

    Args:
        recipe: The owning recipe.
    """
    nutrition_repository.clear_nutrition(recipe=recipe)
