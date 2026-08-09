"""Validation for recipe images."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from apps.common.validators.image_validator import validate_uploaded_image
from apps.recipes.constants import (
    ALLOWED_RECIPE_IMAGE_EXTENSIONS,
    ALLOWED_RECIPE_IMAGE_FORMATS,
    MAX_IMAGES_PER_RECIPE,
    RECIPE_IMAGE_MAX_SIZE_BYTES,
)


def validate_recipe_image(uploaded_file: Any, *, label: str = "Image") -> None:
    """Validate an uploaded recipe image.

    Delegates to the shared validator, which performs the byte-level format
    check. The extension allow-list excludes SVG, which can carry script.

    Args:
        uploaded_file: The uploaded file object.
        label: Noun used in error messages.

    Raises:
        ValidationError: If the file is not an acceptable image.
    """
    validate_uploaded_image(
        uploaded_file,
        max_bytes=RECIPE_IMAGE_MAX_SIZE_BYTES,
        allowed_extensions=ALLOWED_RECIPE_IMAGE_EXTENSIONS,
        allowed_formats=ALLOWED_RECIPE_IMAGE_FORMATS,
        label=label,
    )


def validate_gallery_capacity(*, current_count: int) -> None:
    """Check that another gallery image may be added.

    Args:
        current_count: How many images the recipe already has.

    Raises:
        ValidationError: If the recipe is already at capacity.
    """
    if current_count >= MAX_IMAGES_PER_RECIPE:
        raise ValidationError(
            {
                "image": [
                    f"A recipe can have at most {MAX_IMAGES_PER_RECIPE} gallery images."
                ]
            }
        )
