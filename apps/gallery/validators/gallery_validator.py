"""Validation for gallery uploads."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from apps.common.validators.image_validator import validate_uploaded_image
from apps.gallery.constants import (
    ALLOWED_GALLERY_IMAGE_EXTENSIONS,
    ALLOWED_GALLERY_IMAGE_FORMATS,
    GALLERY_IMAGE_MAX_SIZE_BYTES,
    MAX_IMAGES_PER_POST,
)


def validate_gallery_image(uploaded_file: Any) -> None:
    """Validate an uploaded gallery image before anything touches storage.

    Byte-level format check via the shared validator; rejecting here is
    what guarantees an invalid upload never leaves a file behind.

    Args:
        uploaded_file: The uploaded file object.

    Raises:
        ValidationError: If the file is not an acceptable image.
    """
    validate_uploaded_image(
        uploaded_file,
        max_bytes=GALLERY_IMAGE_MAX_SIZE_BYTES,
        allowed_extensions=ALLOWED_GALLERY_IMAGE_EXTENSIONS,
        allowed_formats=ALLOWED_GALLERY_IMAGE_FORMATS,
        label="Image",
    )


def validate_capacity(*, current_count: int) -> None:
    """Check that another image may be added to the post.

    Args:
        current_count: How many images the post already has.

    Raises:
        ValidationError: If the post is at capacity.
    """
    if current_count >= MAX_IMAGES_PER_POST:
        raise ValidationError(
            {
                "image": [
                    f"A post can have at most {MAX_IMAGES_PER_POST} images."
                ]
            }
        )
