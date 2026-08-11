"""Validation for author-supplied nutrition figures."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError

# Generous ceilings that catch unit mix-ups (grams entered as milligrams) and
# typos, without second-guessing an unusual but legitimate recipe.
FIELD_CEILINGS: dict[str, Decimal] = {
    "serving_size_grams": Decimal("100000"),
    "calories_kcal": Decimal("100000"),
    "protein_g": Decimal("10000"),
    "carbohydrate_g": Decimal("10000"),
    "sugar_g": Decimal("10000"),
    "fat_g": Decimal("10000"),
    "saturated_fat_g": Decimal("10000"),
    "fiber_g": Decimal("10000"),
    "sodium_mg": Decimal("1000000"),
    "cholesterol_mg": Decimal("1000000"),
}


def validate_nutrition(values: Mapping[str, Any]) -> None:
    """Validate nutrition figures.

    Phase 2 performs no arithmetic on these numbers  they are stored and echoed
    back verbatim  so validation is limited to plausibility.

    Args:
        values: Submitted nutrition fields; absent keys are ignored.

    Raises:
        ValidationError: If a figure is negative or implausibly large.
    """
    problems: dict[str, list[str]] = {}

    for field, ceiling in FIELD_CEILINGS.items():
        if field not in values or values[field] is None:
            continue

        amount = Decimal(str(values[field]))
        if amount < 0:
            problems[field] = ["Value cannot be negative."]
        elif amount > ceiling:
            problems[field] = ["Value is implausibly large; check the units."]

    if problems:
        raise ValidationError(problems)
