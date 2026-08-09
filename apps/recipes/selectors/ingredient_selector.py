"""Read-side queries for recipe ingredient lines.

Added in Phase 12 for the substitution endpoint: the recommendation app
needs a recipe's ingredient lines as plain data under the recipes
visibility rule, without importing the model or paying the full detail
prefetch.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.recipes.models import Recipe, RecipeIngredient
from apps.recipes.selectors.recipe_visibility import visible_detail_q


@dataclass(frozen=True)
class IngredientLine:
    """One ingredient line, safe to hand across the app boundary."""

    name: str
    normalized_name: str
    quantity: Decimal | None
    unit: str
    note: str
    group: str
    is_optional: bool


def lines_for_recipe(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> list[IngredientLine] | None:
    """The ingredient lines of one recipe, under the detail visibility rule.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The lines in display order (possibly empty), or ``None`` when the
        recipe is absent or hidden — the caller must not distinguish those
        two cases to the client.
    """
    recipe_id = (
        Recipe.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .values_list("id", flat=True)
        .first()
    )
    if recipe_id is None:
        return None
    return [
        IngredientLine(**row)
        for row in RecipeIngredient.objects.filter(recipe_id=recipe_id)
        .order_by("group", "position", "id")
        .values(
            "name",
            "normalized_name",
            "quantity",
            "unit",
            "note",
            "group",
            "is_optional",
        )
    ]
