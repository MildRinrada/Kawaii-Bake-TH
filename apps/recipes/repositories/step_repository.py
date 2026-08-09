"""Write-side database access for preparation steps."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from apps.recipes.models import Recipe, RecipeStep


def replace_steps(*, recipe: Recipe, steps: Sequence[dict[str, Any]]) -> list[RecipeStep]:
    """Replace every step on a recipe.

    Same full-replacement contract as ingredients: the submitted array *is* the
    order, and ``position`` is assigned from it.

    Args:
        recipe: The owning recipe.
        steps: Steps in display order.

    Returns:
        The created steps.
    """
    RecipeStep.objects.filter(recipe=recipe).delete()
    if not steps:
        return []

    rows = [
        RecipeStep(
            recipe=recipe,
            position=index,
            body=(step.get("body") or "").strip(),
            duration_minutes=step.get("duration_minutes"),
        )
        for index, step in enumerate(steps, start=1)
    ]
    return RecipeStep.objects.bulk_create(rows)
