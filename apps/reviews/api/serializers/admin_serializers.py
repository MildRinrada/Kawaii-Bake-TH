"""Serializers for the staff review-moderation surface."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import PaginatedFilterSerializer
from apps.reviews.api.serializers.review_serializers import ReviewSerializer
from apps.reviews.constants import RATING_MAX, RATING_MIN, ReviewStatus


class AdminReviewSerializer(ReviewSerializer):
    """A review on the staff surface - adds the target's title.

    The flat list spans every recipe and course, so each row must say
    what it reviews without another request.
    """

    recipe_title = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()

    def get_recipe_title(self, obj: Any) -> str | None:
        """Return the recipe title for recipe reviews."""
        return obj.recipe.title if obj.recipe_id else None

    def get_course_title(self, obj: Any) -> str | None:
        """Return the course title for course reviews."""
        return obj.course.title if obj.course_id else None


class AdminReviewFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the flat review list."""

    rating = serializers.IntegerField(
        min_value=RATING_MIN, max_value=RATING_MAX, required=False
    )
    status = serializers.ChoiceField(
        choices=ReviewStatus.choices, required=False, allow_blank=True
    )
    target = serializers.ChoiceField(
        choices=("recipe", "course"), required=False, allow_blank=True
    )
    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    username = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
