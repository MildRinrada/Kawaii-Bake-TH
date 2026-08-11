"""Shared validation for uploaded images.

One implementation, used by every app that accepts an image. A copy-pasted
security control is a control that drifts: the copies diverge, and the weaker
one becomes the attack surface.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


def validate_uploaded_image(
    uploaded_file: Any,
    *,
    max_bytes: int,
    allowed_extensions: Collection[str],
    allowed_formats: Collection[str],
    label: str = "Image",
) -> None:
    """Validate an uploaded image file.

    Checks size, extension, and  critically  the actual decoded image format.
    The ``content_type`` header is client-supplied and is never trusted. SVG is
    excluded by every caller's allow-list because it can carry script and would
    be stored XSS.

    Args:
        uploaded_file: The uploaded file object.
        max_bytes: Maximum permitted size in bytes.
        allowed_extensions: Permitted lowercase file extensions, including the dot.
        allowed_formats: Permitted Pillow format names, for example ``{"JPEG"}``.
        label: Noun used in error messages, for example ``"Avatar"``.

    Raises:
        ValidationError: If the file is too large, has a disallowed extension, or
            is not a decodable image in an allowed format.
    """
    if uploaded_file.size > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise ValidationError(f"{label} must be smaller than {limit_mb:.0f} MB.")

    extension = Path(uploaded_file.name or "").suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"{label} must be one of: {allowed}.")

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError(f"{label} is not a readable image file.") from exc
    finally:
        uploaded_file.seek(0)

    if image_format not in allowed_formats:
        raise ValidationError(f"{label} format is not supported.")
