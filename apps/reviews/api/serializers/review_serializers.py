"""Serializers for reviews and rating statistics."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.recipes.api.serializers.recipe_serializers import AuthorRefSerializer
from apps.reviews.constants import (
    COMMENT_MAX_LENGTH,
    RATING_MAX,
    RATING_MIN,
    ReviewStatus,
)


class ReviewSerializer(serializers.Serializer):
    """One review, reviewer embedded."""

    id = serializers.IntegerField(read_only=True)
    rating = serializers.IntegerField(read_only=True)
    comment = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    target = serializers.CharField(source="target_kind", read_only=True)
    recipe_slug = serializers.SerializerMethodField()
    course_slug = serializers.SerializerMethodField()
    user = AuthorRefSerializer(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_recipe_slug(self, obj: Any) -> str | None:
        """Return the recipe slug for recipe reviews."""
        return obj.recipe.slug if obj.recipe_id else None

    def get_course_slug(self, obj: Any) -> str | None:
        """Return the course slug for course reviews."""
        return obj.course.slug if obj.course_id else None


class ReviewCreateSerializer(StrictSerializer):
    """Validates a review creation payload."""

    rating = serializers.IntegerField(min_value=RATING_MIN, max_value=RATING_MAX)
    comment = serializers.CharField(
        max_length=COMMENT_MAX_LENGTH, required=False, allow_blank=True
    )


class ReviewUpdateSerializer(StrictSerializer):
    """Validates a partial review update.

    ``status`` is moderation  accepted here for shape, enforced staff-only
    in the service. ``deleted`` is never settable through PATCH; deletion has
    its own verb.
    """

    rating = serializers.IntegerField(
        min_value=RATING_MIN, max_value=RATING_MAX, required=False
    )
    comment = serializers.CharField(
        max_length=COMMENT_MAX_LENGTH, required=False, allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=[
            (ReviewStatus.ACTIVE, "active"),
            (ReviewStatus.HIDDEN, "hidden"),
        ],
        required=False,
    )


class RatingSummarySerializer(serializers.Serializer):
    """Aggregate rating figures for one target."""

    average = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True, allow_null=True
    )
    count = serializers.IntegerField(read_only=True)
    distribution = serializers.DictField(
        child=serializers.IntegerField(), read_only=True
    )
