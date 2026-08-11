"""Serializers for recipe categories."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.recipe_categories.constants import (
    CATEGORY_DESCRIPTION_MAX_LENGTH,
    CATEGORY_ICON_MAX_LENGTH,
    CATEGORY_NAME_MAX_LENGTH,
    CATEGORY_SLUG_MAX_LENGTH,
)


class _ImageUrlMixin(serializers.Serializer):
    """Adds an absolute ``image_url`` - the frontend is another origin."""

    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj: Any) -> str | None:
        """Return the absolute tile-photo URL, or ``None`` when unset."""
        image = getattr(obj, "image", None)
        if not image:
            return None
        request = self.context.get("request")
        url = image.url
        return request.build_absolute_uri(url) if request is not None else url


class CategoryRefSerializer(serializers.Serializer):
    """A category reference embedded in another payload.

    Kept to the fields in ``category_selector.REFERENCE_FIELDS`` so it is always
    safe to render from ``ref_queryset()``.
    """

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)


class CategorySerializer(_ImageUrlMixin):
    """A category in the category listing."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)
    display_order = serializers.IntegerField(read_only=True)
    recipe_count = serializers.IntegerField(read_only=True)


class AdminCategorySerializer(CategorySerializer):
    """A category on the staff surface - adds curation state."""

    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class CategoryCreateSerializer(StrictSerializer):
    """Multipart payload for creating a category."""

    name = serializers.CharField(max_length=CATEGORY_NAME_MAX_LENGTH)
    slug = serializers.SlugField(
        max_length=CATEGORY_SLUG_MAX_LENGTH,
        required=False,
        allow_blank=True,
        allow_unicode=True,
    )
    description = serializers.CharField(
        max_length=CATEGORY_DESCRIPTION_MAX_LENGTH, required=False, allow_blank=True
    )
    icon = serializers.CharField(
        max_length=CATEGORY_ICON_MAX_LENGTH, required=False, allow_blank=True
    )
    display_order = serializers.IntegerField(required=False, min_value=0)
    is_active = serializers.BooleanField(required=False)
    image = serializers.ImageField(required=False)


class CategoryUpdateSerializer(StrictSerializer):
    """Multipart payload for editing a category; absent keys are unchanged.

    ``image: null`` removes the tile photo.
    """

    name = serializers.CharField(max_length=CATEGORY_NAME_MAX_LENGTH, required=False)
    slug = serializers.SlugField(
        max_length=CATEGORY_SLUG_MAX_LENGTH, required=False, allow_unicode=True
    )
    description = serializers.CharField(
        max_length=CATEGORY_DESCRIPTION_MAX_LENGTH, required=False, allow_blank=True
    )
    icon = serializers.CharField(
        max_length=CATEGORY_ICON_MAX_LENGTH, required=False, allow_blank=True
    )
    display_order = serializers.IntegerField(required=False, min_value=0)
    is_active = serializers.BooleanField(required=False)
    image = serializers.ImageField(required=False, allow_null=True)
