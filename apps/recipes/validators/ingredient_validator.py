"""Domain validation for ingredient lines."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError

from apps.recipes.constants import MAX_INGREDIENTS_PER_RECIPE, Unit
from apps.recipes.utils import normalize_ingredient_name


def validate_lines(lines: Sequence[dict[str, Any]]) -> None:
    """Validate a full set of ingredient lines.

    An empty list is permitted here: a draft must be saveable while incomplete.
    The "at least one ingredient" rule belongs to ``publish_validator``.

    Args:
        lines: Submitted ingredient lines.

    Raises:
        ValidationError: If the set is too large, a name is blank, a quantity is
            not positive, a unit is unknown, or two lines name the same thing.
    """
    if len(lines) > MAX_INGREDIENTS_PER_RECIPE:
        raise ValidationError(
            {
                "ingredients": [
                    f"A recipe can have at most {MAX_INGREDIENTS_PER_RECIPE} ingredients."
                ]
            }
        )

    valid_units = {choice.value for choice in Unit}
    seen: set[str] = set()

    for index, line in enumerate(lines):
        name = (line.get("name") or "").strip()
        if not name:
            raise ValidationError(
                {"ingredients": [f"Ingredient {index + 1} needs a name."]}
            )

        quantity = line.get("quantity")
        if quantity is not None and Decimal(str(quantity)) <= 0:
            raise ValidationError(
                {
                    "ingredients": [
                        f"Ingredient {index + 1} must have a positive quantity, "
                        "or none at all for 'to taste'."
                    ]
                }
            )

        unit = line.get("unit")
        if unit and unit not in valid_units:
            raise ValidationError(
                {"ingredients": [f"Ingredient {index + 1} has an unknown unit."]}
            )

        normalized = normalize_ingredient_name(name)
        if normalized in seen:
            raise ValidationError(
                {"ingredients": [f"'{name}' is listed more than once."]}
            )
        seen.add(normalized)
