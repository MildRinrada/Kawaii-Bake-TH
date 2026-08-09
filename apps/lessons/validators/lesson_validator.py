"""Domain validation for lessons."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError

from apps.lessons.constants import LESSON_TITLE_MIN_LENGTH, VideoProvider


def validate_title(title: str) -> None:
    """Validate a lesson title.

    Raises:
        ValidationError: If blank or too short.
    """
    if not title or not title.strip():
        raise ValidationError({"title": ["Title cannot be blank."]})
    if len(title.strip()) < LESSON_TITLE_MIN_LENGTH:
        raise ValidationError(
            {"title": [f"Title must be at least {LESSON_TITLE_MIN_LENGTH} characters long."]}
        )


def validate_video(data: Mapping[str, Any]) -> None:
    """Validate the video metadata combination.

    Raises:
        ValidationError: If a provider is named without a URL, or a URL is not
            https.
    """
    url = (data.get("video_url") or "").strip()
    provider = data.get("video_provider") or ""

    if provider and not url:
        raise ValidationError(
            {"video_url": ["A video URL is required when a provider is set."]}
        )
    if url and not url.startswith("https://"):
        raise ValidationError({"video_url": ["Video URLs must use https."]})
    if url and provider and provider not in VideoProvider.values:
        raise ValidationError({"video_provider": ["Unknown video provider."]})


def validate_core(data: Mapping[str, Any]) -> None:
    """Run every lesson rule present in ``data``.

    Args:
        data: Submitted lesson fields; absent keys are skipped.

    Raises:
        ValidationError: If any rule fails.
    """
    if "title" in data:
        validate_title(data["title"])
    if "video_url" in data or "video_provider" in data:
        validate_video(data)
    if "duration_minutes" in data and (data["duration_minutes"] or 0) < 0:
        raise ValidationError({"duration_minutes": ["Duration cannot be negative."]})
