"""Domain validation rules for recipe categories."""

from __future__ import annotations

from typing import Any

from apps.common.validators.image_validator import validate_uploaded_image
from apps.recipe_categories.constants import (
    ALLOWED_CATEGORY_IMAGE_EXTENSIONS,
    ALLOWED_CATEGORY_IMAGE_FORMATS,
    CATEGORY_IMAGE_MAX_SIZE_BYTES,
)


def validate_category_image(uploaded_file: Any) -> None:
    """Validate an uploaded category tile photo.

    Delegates to the shared image validator so every app enforces
    byte-level format checking from a single implementation.

    Args:
        uploaded_file: The uploaded file object.

    Raises:
        django.core.exceptions.ValidationError: If the file is too large, has a
            disallowed extension, or is not a decodable image in an allowed
            format.
    """
    validate_uploaded_image(
        uploaded_file,
        max_bytes=CATEGORY_IMAGE_MAX_SIZE_BYTES,
        allowed_extensions=ALLOWED_CATEGORY_IMAGE_EXTENSIONS,
        allowed_formats=ALLOWED_CATEGORY_IMAGE_FORMATS,
        label="Category image",
    )
