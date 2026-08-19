"""Expand the compact seed literals into service-shaped payloads.

The data modules are written for a human to read and edit: an ingredient line
is a tuple, a step is a bare string when it needs no timer, and nutrition is a
fixed five-number tuple. Turning those into the dictionaries the recipes
services already accept is this module's only job, so the data files never
repeat a key name a hundred and forty times.

Nothing here touches the database or imports Django, which is what lets the
tests exercise the whole seed set without a migration run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Most bakery quantities are weights, so `("แป้งขนมปัง", 300)` is the common
# case and spelling the unit out every time would be noise.
DEFAULT_UNIT = "g"

# The order of the `nutrition` tuple in every data module. Per serving.
NUTRITION_FIELDS: tuple[str, ...] = (
    "calories_kcal",
    "protein_g",
    "carbohydrate_g",
    "sugar_g",
    "fat_g",
)


def _ingredient(line: Sequence[Any] | Mapping[str, Any]) -> dict[str, Any]:
    """Expand one ingredient literal.

    Accepts ``(name,)`` through
    ``(name, quantity, unit, note, group, is_optional)``. A quantity of ``None``
    means an unmeasured amount, which is exactly what the model documents for
    "to taste" lines.

    Args:
        line: The ingredient tuple, or an already-expanded mapping.

    Returns:
        A line in the shape ``ingredient_repository.replace_ingredients`` wants.
    """
    if isinstance(line, Mapping):
        return dict(line)

    name, quantity, unit, note, group, optional = (
        *line,
        *([None] * (6 - len(line))),
    )
    return {
        "name": name,
        "quantity": quantity,
        "unit": DEFAULT_UNIT if unit is None and quantity is not None else (unit or ""),
        "note": note or "",
        "group": group or "",
        "is_optional": bool(optional),
    }


def _step(item: str | Sequence[Any] | Mapping[str, Any]) -> dict[str, Any]:
    """Expand one step literal.

    Accepts a bare string, ``(body, duration_minutes)``, or a mapping. The
    duration is optional because only waiting steps  proofing, chilling,
    baking  are worth putting a timer on.

    Args:
        item: The step literal.

    Returns:
        A step in the shape ``step_repository.replace_steps`` wants.
    """
    if isinstance(item, Mapping):
        return dict(item)
    if isinstance(item, str):
        return {"body": item, "duration_minutes": None}

    body, duration = (*item, *([None] * (2 - len(item))))
    return {"body": body, "duration_minutes": duration}


def _nutrition(values: Sequence[Any] | Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Expand the nutrition literal.

    Args:
        values: The five-number tuple, a mapping, or ``None`` when the seed
            author did not estimate the figures.

    Returns:
        Nutrition fields keyed by column name, or ``None``.
    """
    if values is None:
        return None
    if isinstance(values, Mapping):
        return dict(values)
    return dict(zip(NUTRITION_FIELDS, values, strict=True))


def build_payload(*, seed: Mapping[str, Any], category_slug: str) -> dict[str, Any]:
    """Turn one seed literal into a create-recipe payload.

    Args:
        seed: One entry of a data module's ``RECIPES`` list.
        category_slug: The category the data module belongs to.

    Returns:
        A payload carrying the same keys the recipes API accepts, plus the
        explicit ``slug`` the seed owns so re-running the command is idempotent.
    """
    prep = seed.get("prep", 0)
    cook = seed.get("cook", 0)

    return {
        "slug": seed["slug"],
        "title": seed["title"],
        "summary": seed.get("summary", ""),
        "description": seed.get("description", ""),
        "difficulty": seed.get("difficulty", "easy"),
        "prep_minutes": prep,
        "cook_minutes": cook,
        "servings": seed.get("servings", 4),
        "category_slugs": list(seed.get("categories") or [category_slug]),
        "ingredients": [_ingredient(line) for line in seed.get("ingredients", ())],
        "steps": [_step(item) for item in seed.get("steps", ())],
        "nutrition": _nutrition(seed.get("nutrition")),
    }
