"""Pure helpers for the courses app."""

from __future__ import annotations

import secrets

from django.utils.text import slugify

from apps.courses.constants import (
    COURSE_SLUG_BASE_MAX_LENGTH,
    COURSE_SLUG_SUFFIX_BYTES,
    RESERVED_COURSE_SLUGS,
)


def build_course_slug_base(title: str) -> str:
    """Derive a URL slug base from a course title.

    Same contract as the recipes helper: ``allow_unicode=True`` keeps Thai
    (plain ``slugify`` would return ``""`` for a Thai title), the result is
    lossy for combining marks, and unusable titles yield an empty base so the
    caller falls back to a random slug.

    Args:
        title: The course title.

    Returns:
        A slug base, or an empty string when the title yields nothing usable.
    """
    base = slugify(title, allow_unicode=True)
    base = base[:COURSE_SLUG_BASE_MAX_LENGTH].rstrip("-")

    if not base or base.isdigit() or base in RESERVED_COURSE_SLUGS:
        return ""
    return base


def course_slug_with_suffix(base: str) -> str:
    """Append a random suffix to a slug base.

    Random rather than a counter: counting needs a query that races under
    concurrent writes and leaks how many similarly titled courses exist.

    Args:
        base: The slug base, possibly empty.

    Returns:
        A slug candidate with a random suffix.
    """
    suffix = secrets.token_hex(COURSE_SLUG_SUFFIX_BYTES)
    return f"{base}-{suffix}" if base else f"course-{suffix}"
