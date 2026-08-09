"""Constants for the recipe categories app."""

from __future__ import annotations

CATEGORY_NAME_MAX_LENGTH = 80
CATEGORY_SLUG_MAX_LENGTH = 80
CATEGORY_DESCRIPTION_MAX_LENGTH = 300
CATEGORY_ICON_MAX_LENGTH = 40

# Ordering applied to every category listing.
CATEGORY_DEFAULT_ORDERING = ("display_order", "name")
