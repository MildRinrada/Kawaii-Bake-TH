"""Serializers for recipe categories."""

from __future__ import annotations

from rest_framework import serializers


class CategoryRefSerializer(serializers.Serializer):
    """A category reference embedded in another payload.

    Kept to the fields in ``category_selector.REFERENCE_FIELDS`` so it is always
    safe to render from ``ref_queryset()``.
    """

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)


class CategorySerializer(serializers.Serializer):
    """A category in the category listing."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)
    display_order = serializers.IntegerField(read_only=True)
    recipe_count = serializers.IntegerField(read_only=True)
