"""Serializers for the favorites list."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.favorites.constants import FavoriteTargetKind


class FavoriteItemSerializer(serializers.Serializer):
    """One favorite with its target card embedded.

    The cards come from the content apps' own list serializers, batch-fetched
    by the view  this serializer only stitches. The queryset already
    filtered targets by visibility, so a card is always present.
    """

    type = serializers.CharField(source="target_kind", read_only=True)
    favorited_at = serializers.DateTimeField(source="created_at", read_only=True)
    recipe = serializers.SerializerMethodField()
    course = serializers.SerializerMethodField()

    def get_recipe(self, obj: Any) -> dict[str, Any] | None:
        """Return the recipe card for recipe favorites."""
        return self.context.get("recipe_cards", {}).get(obj.recipe_id)

    def get_course(self, obj: Any) -> dict[str, Any] | None:
        """Return the course card for course favorites."""
        return self.context.get("course_cards", {}).get(obj.course_id)


class FavoriteListQuerySerializer(StrictSerializer):
    """Validates the query string of the favorites list."""

    type = serializers.ChoiceField(
        choices=FavoriteTargetKind.choices, required=False
    )
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)
