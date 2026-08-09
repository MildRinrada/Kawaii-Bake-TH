"""Read serializers for courses.

Plain ``Serializer`` only; every relation rendered here is prefetched or
annotated by the selector, and the query-count test enforces it.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.recipe_categories.api.serializers import CategoryRefSerializer
from apps.recipes.api.serializers.recipe_serializers import (
    AuthorRefSerializer,
    ImageUrlMixin,
)


class CourseListItemSerializer(ImageUrlMixin):
    """One course in a listing."""

    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    difficulty = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    visibility = serializers.CharField(read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    lesson_count = serializers.IntegerField(
        source="published_lesson_count", read_only=True
    )
    total_duration_minutes = serializers.IntegerField(
        source="published_duration_minutes", read_only=True
    )
    # Aggregates are stored columns maintained by the reviews app
    # (ADR 0021) — no join, no N+1. Average is null when unreviewed.
    rating_average = serializers.SerializerMethodField()
    rating_count = serializers.IntegerField(read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    instructor = AuthorRefSerializer(read_only=True)
    categories = CategoryRefSerializer(many=True, read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    def get_rating_average(self, obj: Any) -> float | None:
        """Return the stored average as a float, or ``None`` when unreviewed."""
        return float(obj.rating_average) if obj.rating_average is not None else None

    def get_thumbnail_url(self, obj: Any) -> str | None:
        """Return the absolute thumbnail URL, if any."""
        return self._absolute(obj.thumbnail)

    def get_is_enrolled(self, obj: Any) -> bool:
        """Return the viewer's enrollment flag from the selector annotation."""
        return bool(getattr(obj, "viewer_is_enrolled", False))

    def get_is_completed(self, obj: Any) -> bool:
        """Return the viewer's completion flag from the selector annotation."""
        return bool(getattr(obj, "viewer_has_completed", False))


class CourseDetailSerializer(CourseListItemSerializer):
    """A full course."""

    description = serializers.CharField(read_only=True)
