"""Domain validation for recipe core fields.

These run on **every** write. Completeness rules that only matter for a
published recipe live in ``publish_validator``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError

from apps.recipes.constants import (
    MAX_CATEGORIES_PER_RECIPE,
    MAX_SERVINGS,
    MAX_TOTAL_MINUTES,
    MIN_SERVINGS,
    RESERVED_RECIPE_SLUGS,
    TITLE_MIN_LENGTH,
)


def validate_title(title: str) -> None:
    """Validate a recipe title.

    Args:
        title: The submitted title.

    Raises:
        ValidationError: If the title is blank or too short.
    """
    if not title or not title.strip():
        raise ValidationError({"title": ["Title cannot be blank."]})
    if len(title.strip()) < TITLE_MIN_LENGTH:
        raise ValidationError(
            {"title": [f"Title must be at least {TITLE_MIN_LENGTH} characters long."]}
        )


def validate_times(*, prep_minutes: int, cook_minutes: int) -> None:
    """Validate preparation and cooking times.

    Args:
        prep_minutes: Preparation time in minutes.
        cook_minutes: Cooking time in minutes.

    Raises:
        ValidationError: If a time is negative or the total is implausible.
    """
    errors: dict[str, list[str]] = {}

    if prep_minutes < 0:
        errors["prep_minutes"] = ["Preparation time cannot be negative."]
    if cook_minutes < 0:
        errors["cook_minutes"] = ["Cooking time cannot be negative."]
    if errors:
        raise ValidationError(errors)

    if prep_minutes + cook_minutes > MAX_TOTAL_MINUTES:
        days = MAX_TOTAL_MINUTES // (60 * 24)
        raise ValidationError(
            {"cook_minutes": [f"Total time cannot exceed {days} days."]}
        )


def validate_servings(servings: int) -> None:
    """Validate the servings count.

    Args:
        servings: Number of servings the recipe yields.

    Raises:
        ValidationError: If outside the permitted range.
    """
    if servings < MIN_SERVINGS or servings > MAX_SERVINGS:
        raise ValidationError(
            {
                "servings": [
                    f"Servings must be between {MIN_SERVINGS} and {MAX_SERVINGS}."
                ]
            }
        )


def validate_slug(slug: str) -> None:
    """Validate a client-supplied slug.

    Args:
        slug: The requested slug.

    Raises:
        ValidationError: If the slug is blank or reserved.
    """
    cleaned = (slug or "").strip().lower()
    if not cleaned:
        raise ValidationError({"slug": ["Slug cannot be blank."]})
    if cleaned in RESERVED_RECIPE_SLUGS:
        raise ValidationError({"slug": ["This URL is reserved. Please choose another."]})


def validate_category_count(slugs: object) -> None:
    """Validate how many categories are being assigned.

    Args:
        slugs: The submitted category slugs.

    Raises:
        ValidationError: If too many categories were supplied.
    """
    if slugs and len(list(slugs)) > MAX_CATEGORIES_PER_RECIPE:
        raise ValidationError(
            {
                "category_slugs": [
                    f"Select at most {MAX_CATEGORIES_PER_RECIPE} categories."
                ]
            }
        )


def validate_core(data: Mapping[str, Any]) -> None:
    """Run every always-on recipe rule present in ``data``.

    Only keys actually supplied are checked, so the same function serves both
    create and partial update.

    Args:
        data: Submitted recipe fields.

    Raises:
        ValidationError: If any rule fails.
    """
    if "title" in data:
        validate_title(data["title"])

    if "prep_minutes" in data or "cook_minutes" in data:
        validate_times(
            prep_minutes=data.get("prep_minutes", 0) or 0,
            cook_minutes=data.get("cook_minutes", 0) or 0,
        )

    if "servings" in data:
        validate_servings(data["servings"])

    if "slug" in data:
        validate_slug(data["slug"])

    if "category_slugs" in data:
        validate_category_count(data["category_slugs"])
