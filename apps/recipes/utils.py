"""Pure helpers for the recipes app: no database, no side effects."""

from __future__ import annotations

import secrets

from django.utils.text import slugify

from apps.common.utils.files import build_upload_path
from apps.common.utils.text import normalize_ingredient_name
from apps.recipes.constants import (
    RESERVED_RECIPE_SLUGS,
    SLUG_BASE_MAX_LENGTH,
    SLUG_SUFFIX_BYTES,
)


def build_slug_base(title: str) -> str:
    """Derive a URL slug base from a recipe title.

    ``allow_unicode=True`` is essential: plain ``slugify`` strips every Thai
    character and returns an empty string, so all Thai-titled recipes would
    silently fall back to a random slug.

    Note that even with it, slugification is **lossy for Thai** — combining tone
    marks and vowel signs are dropped, exactly as accents are dropped from
    Latin text. That is fine for a URL identifier, and it is one more reason
    collisions are resolved with a random suffix rather than a counter.

    Args:
        title: The recipe title.

    Returns:
        A slug base, or an empty string when the title yields nothing usable
        (pure punctuation or emoji, a bare number, or a reserved word).
    """
    base = slugify(title, allow_unicode=True)
    base = base[:SLUG_BASE_MAX_LENGTH].rstrip("-")

    if not base or base.isdigit() or base in RESERVED_RECIPE_SLUGS:
        return ""
    return base


def slug_with_suffix(base: str) -> str:
    """Append a random suffix to a slug base.

    A random suffix rather than an incrementing counter: counting needs a query
    (which races under concurrent writes) and leaks how many similarly titled
    recipes exist.

    Args:
        base: The slug base, possibly empty.

    Returns:
        A slug candidate with a random suffix.
    """
    suffix = secrets.token_hex(SLUG_SUFFIX_BYTES)
    return f"{base}-{suffix}" if base else f"recipe-{suffix}"


# Re-exported for existing callers; `build_upload_path` moved to
# `apps.common.utils.files` when the courses app needed it too, and
# `normalize_ingredient_name` to `apps.common.utils.text` when the
# recommendation app's substitution lookup needed the same rule.
__all__ = ["build_slug_base", "slug_with_suffix", "normalize_ingredient_name", "build_upload_path"]
