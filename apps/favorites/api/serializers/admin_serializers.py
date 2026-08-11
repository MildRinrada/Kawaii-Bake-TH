"""Serializers for the staff favorites surface."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import PaginatedFilterSerializer
from apps.favorites.constants import FavoriteTargetKind


class AdminFavoriteSerializer(serializers.Serializer):
    """One favorite row across users - owner and target, no cards."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True, source="user.username")
    display_name = serializers.SerializerMethodField()
    type = serializers.CharField(source="target_kind", read_only=True)
    target_title = serializers.SerializerMethodField()
    target_slug = serializers.SerializerMethodField()
    favorited_at = serializers.DateTimeField(source="created_at", read_only=True)

    def get_display_name(self, obj: Any) -> str:
        """Return the owner's display name, falling back to the handle."""
        profile = getattr(obj.user, "profile", None)
        return (profile.display_name if profile else "") or obj.user.username

    def get_target_title(self, obj: Any) -> str | None:
        """Return the favorited item's title."""
        if obj.recipe_id:
            return obj.recipe.title
        if obj.course_id:
            return obj.course.title
        return None

    def get_target_slug(self, obj: Any) -> str | None:
        """Return the favorited item's slug."""
        if obj.recipe_id:
            return obj.recipe.slug
        if obj.course_id:
            return obj.course.slug
        return None


class FavoriteTopEntrySerializer(serializers.Serializer):
    """One row of a most-favorited ranking."""

    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    count = serializers.IntegerField(read_only=True)


class FavoriteTopSerializer(serializers.Serializer):
    """The most-favorited rankings, one list per target kind."""

    recipes = FavoriteTopEntrySerializer(many=True, read_only=True)
    courses = FavoriteTopEntrySerializer(many=True, read_only=True)


class AdminFavoriteFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the cross-user favorites list."""

    type = serializers.ChoiceField(
        choices=FavoriteTargetKind.choices, required=False, allow_blank=True
    )
    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
