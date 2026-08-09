"""Write-side database access for ingredient lines."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from apps.recipes.models import Recipe, RecipeIngredient
from apps.recipes.utils import normalize_ingredient_name


def replace_ingredients(
    *, recipe: Recipe, lines: Sequence[dict[str, Any]]
) -> list[RecipeIngredient]:
    """Replace every ingredient line on a recipe.

    Full replacement rather than per-item diffing: the editor holds the whole
    array anyway, reordering becomes free, and per-item updates would need
    stable child ids plus an ownership check on every one of them.

    ``position`` is assigned from the array order — never taken from the client,
    which routinely sends duplicate or gapped values.

    Args:
        recipe: The owning recipe.
        lines: Ingredient lines in display order.

    Returns:
        The created lines.
    """
    RecipeIngredient.objects.filter(recipe=recipe).delete()
    if not lines:
        return []

    rows = [
        RecipeIngredient(
            recipe=recipe,
            name=(line.get("name") or "").strip(),
            normalized_name=normalize_ingredient_name(line.get("name") or ""),
            quantity=line.get("quantity"),
            unit=line.get("unit") or "",
            note=(line.get("note") or "").strip(),
            group=(line.get("group") or "").strip(),
            is_optional=bool(line.get("is_optional", False)),
            position=index,
        )
        for index, line in enumerate(lines, start=1)
    ]
    return RecipeIngredient.objects.bulk_create(rows)
