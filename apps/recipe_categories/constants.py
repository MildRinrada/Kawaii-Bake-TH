"""Constants for the recipe categories app."""

from __future__ import annotations

CATEGORY_NAME_MAX_LENGTH = 80
CATEGORY_SLUG_MAX_LENGTH = 80
CATEGORY_DESCRIPTION_MAX_LENGTH = 300
CATEGORY_ICON_MAX_LENGTH = 40

# Ordering applied to every category listing.
CATEGORY_DEFAULT_ORDERING = ("display_order", "name")

# Category tile photo uploads. The photo is presentation only, so the
# avatar-class limits are enough; SVG is excluded everywhere (stored XSS).
CATEGORY_IMAGE_UPLOAD_DIR = "categories"
CATEGORY_IMAGE_MAX_SIZE_BYTES = 4 * 1024 * 1024
ALLOWED_CATEGORY_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ALLOWED_CATEGORY_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
