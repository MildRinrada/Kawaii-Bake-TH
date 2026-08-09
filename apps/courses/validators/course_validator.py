"""Domain validation for course core fields — runs on every write."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError

from apps.courses.constants import (
    COURSE_TITLE_MIN_LENGTH,
    MAX_CATEGORIES_PER_COURSE,
    RESERVED_COURSE_SLUGS,
)


def validate_title(title: str) -> None:
    """Validate a course title.

    Args:
        title: The submitted title.

    Raises:
        ValidationError: If blank or too short.
    """
    if not title or not title.strip():
        raise ValidationError({"title": ["Title cannot be blank."]})
    if len(title.strip()) < COURSE_TITLE_MIN_LENGTH:
        raise ValidationError(
            {"title": [f"Title must be at least {COURSE_TITLE_MIN_LENGTH} characters long."]}
        )


def validate_slug(slug: str) -> None:
    """Validate a client-supplied slug.

    Args:
        slug: The requested slug.

    Raises:
        ValidationError: If blank or reserved.
    """
    cleaned = (slug or "").strip().lower()
    if not cleaned:
        raise ValidationError({"slug": ["Slug cannot be blank."]})
    if cleaned in RESERVED_COURSE_SLUGS:
        raise ValidationError({"slug": ["This URL is reserved. Please choose another."]})


def validate_category_count(slugs: object) -> None:
    """Validate how many categories are being assigned.

    Args:
        slugs: The submitted category slugs.

    Raises:
        ValidationError: If too many were supplied.
    """
    if slugs and len(list(slugs)) > MAX_CATEGORIES_PER_COURSE:
        raise ValidationError(
            {"category_slugs": [f"Select at most {MAX_CATEGORIES_PER_COURSE} categories."]}
        )


def validate_core(data: Mapping[str, Any]) -> None:
    """Run every always-on course rule present in ``data``.

    Args:
        data: Submitted course fields; absent keys are skipped so the same
            function serves create and partial update.

    Raises:
        ValidationError: If any rule fails.
    """
    if "title" in data:
        validate_title(data["title"])
    if "slug" in data:
        validate_slug(data["slug"])
    if "category_slugs" in data:
        validate_category_count(data["category_slugs"])
