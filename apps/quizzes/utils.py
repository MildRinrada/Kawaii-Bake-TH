"""Pure helpers for the quizzes app."""

from __future__ import annotations

import secrets

from django.utils.text import slugify

from apps.quizzes.constants import (
    QUIZ_SLUG_BASE_MAX_LENGTH,
    QUIZ_SLUG_SUFFIX_BYTES,
    RESERVED_QUIZ_SLUGS,
)


def build_quiz_slug_base(title: str) -> str:
    """Derive a URL slug base from a quiz title.

    Same contract as the recipes/courses helpers: ``allow_unicode=True`` keeps
    Thai, the result is lossy for combining marks, and unusable titles yield
    an empty base so the caller falls back to a random slug.

    Args:
        title: The quiz title.

    Returns:
        A slug base, or an empty string when the title yields nothing usable.
    """
    base = slugify(title, allow_unicode=True)
    base = base[:QUIZ_SLUG_BASE_MAX_LENGTH].rstrip("-")

    if not base or base.isdigit() or base in RESERVED_QUIZ_SLUGS:
        return ""
    return base


def quiz_slug_with_suffix(base: str) -> str:
    """Append a random suffix to a slug base.

    Random rather than a counter: counting needs a query that races under
    concurrent writes and leaks how many similarly titled quizzes exist.

    Args:
        base: The slug base, possibly empty.

    Returns:
        A slug candidate with a random suffix.
    """
    suffix = secrets.token_hex(QUIZ_SLUG_SUFFIX_BYTES)
    return f"{base}-{suffix}" if base else f"quiz-{suffix}"
