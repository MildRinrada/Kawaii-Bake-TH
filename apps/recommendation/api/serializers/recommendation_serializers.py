"""Serializers for the recommendation feeds."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer


class RecommendedRecipeSerializer(serializers.Serializer):
    """One recommended recipe: the public card plus its reason codes.

    The card comes from the recipes app's own list serializer, batch-fetched
    by the view (the favorites stitching pattern) — this serializer never
    touches the ORM. Reasons are aggregate evidence codes; no score and no
    raw behavior ever appear here (ADR 0018 §10).
    """

    reasons = serializers.ListField(child=serializers.CharField(), read_only=True)
    recipe = serializers.SerializerMethodField()

    def get_recipe(self, obj: Any) -> dict[str, Any] | None:
        """Return the recipe card for this recommendation."""
        return self.context.get("recipe_cards", {}).get(obj.target_id)


class RecommendedCourseSerializer(serializers.Serializer):
    """One recommended course — the courses mirror of the recipe item."""

    reasons = serializers.ListField(child=serializers.CharField(), read_only=True)
    course = serializers.SerializerMethodField()

    def get_course(self, obj: Any) -> dict[str, Any] | None:
        """Return the course card for this recommendation."""
        return self.context.get("course_cards", {}).get(obj.target_id)


class RecommendationListQuerySerializer(StrictSerializer):
    """Validates the query string of both recommendation feeds.

    Pagination only — scores, weights and features are not client inputs,
    by design.
    """

    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)
