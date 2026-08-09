"""Domain validation rules for profiles and preferences."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.common.validators.image_validator import validate_uploaded_image
from apps.users.constants import (
    ALLOWED_AVATAR_EXTENSIONS,
    ALLOWED_AVATAR_FORMATS,
    AVATAR_MAX_SIZE_BYTES,
    MAX_AGE_YEARS,
    MAX_DIETARY_RESTRICTIONS,
    MAX_FAVORITE_CATEGORIES,
    MIN_AGE_YEARS,
    DietaryRestriction,
)


def validate_avatar(uploaded_file: Any) -> None:
    """Validate an uploaded avatar image.

    Delegates to the shared image validator so that this app and the recipes
    app enforce byte-level format checking from a single implementation.

    Args:
        uploaded_file: The uploaded file object.

    Raises:
        ValidationError: If the file is too large, has a disallowed extension,
            or is not a decodable image in an allowed format.
    """
    validate_uploaded_image(
        uploaded_file,
        max_bytes=AVATAR_MAX_SIZE_BYTES,
        allowed_extensions=ALLOWED_AVATAR_EXTENSIONS,
        allowed_formats=ALLOWED_AVATAR_FORMATS,
        label="Avatar",
    )


def validate_favorite_categories(values: Any) -> list[str]:
    """Normalise the favourite-category slug list: shape, count, duplicates.

    **Existence** is no longer decided here (Phase 14): the profile service
    resolves the slugs against the live ``recipe_categories`` taxonomy, so
    a newly added category is selectable without a code change and a
    removed one stops validating — a frozen enum can do neither.

    Args:
        values: The submitted category slugs.

    Returns:
        The de-duplicated list, order preserved.

    Raises:
        ValidationError: If the payload is not a list of strings or exceeds
            the maximum count.
    """
    return _validate_slug_list(
        values,
        allowed=None,
        maximum=MAX_FAVORITE_CATEGORIES,
        label="baking category",
    )


def validate_dietary_restrictions(values: Any) -> list[str]:
    """Validate and normalise the dietary restrictions list.

    Args:
        values: The submitted restriction slugs.

    Returns:
        The de-duplicated list of valid slugs.

    Raises:
        ValidationError: If the payload is invalid.
    """
    return _validate_slug_list(
        values,
        allowed={choice.value for choice in DietaryRestriction},
        maximum=MAX_DIETARY_RESTRICTIONS,
        label="dietary restriction",
    )


def _validate_slug_list(
    values: Any, *, allowed: set[str] | None, maximum: int, label: str
) -> list[str]:
    """Validate a list of slugs.

    Args:
        values: The submitted values.
        allowed: The permitted slugs, or ``None`` when membership is checked
            elsewhere (against a live table rather than an enum).
        maximum: Maximum number of entries.
        label: Human-readable noun used in error messages.

    Returns:
        The de-duplicated list, order preserved.

    Raises:
        ValidationError: If the payload is malformed or contains unknown slugs.
    """
    if not isinstance(values, list):
        raise ValidationError(f"Expected a list of {label} values.")
    if len(values) > maximum:
        raise ValidationError(f"Select at most {maximum} {label} values.")

    seen: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValidationError(f"Each {label} must be a string.")
        if allowed is not None and value not in allowed:
            raise ValidationError(f"'{value}' is not a valid {label}.")
        if value not in seen:
            seen.append(value)
    return seen


def validate_birthday(value: date | None) -> None:
    """Validate a birthday.

    Args:
        value: The submitted date, or ``None`` to clear it.

    Raises:
        ValidationError: If the date is in the future, implies an implausible
            age, or is below the minimum sign-up age.
    """
    if value is None:
        return

    today = timezone.localdate()
    if value > today:
        raise ValidationError("Birthday cannot be in the future.")

    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < MIN_AGE_YEARS:
        raise ValidationError(f"You must be at least {MIN_AGE_YEARS} years old.")
    if age > MAX_AGE_YEARS:
        raise ValidationError("Birthday is not a plausible date.")
