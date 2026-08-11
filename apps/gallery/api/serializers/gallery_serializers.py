"""Serializers for gallery payloads.

One public shape per endpoint (no per-viewer conditional fields). The
author is public profile info  handle, display name, avatar  the same
three fields every other content app already shows for an author or
instructor (see ``apps.recipes.api.serializers.recipe_serializers.
AuthorRefSerializer``, the precedent this mirrors). None of it is the
email/identity data the platform actually treats as private.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.gallery.constants import (
    CAPTION_MAX_LENGTH,
    MAX_IMAGES_PER_POST,
    GalleryPostStatus,
)
from apps.gallery.models import GalleryImage


class GalleryImageSerializer(serializers.Serializer):
    """One image of a post."""

    id = serializers.IntegerField(read_only=True)
    url = serializers.SerializerMethodField()
    position = serializers.IntegerField(read_only=True)

    def get_url(self, obj: GalleryImage) -> str:
        """Absolute media URL  the frontend runs on another origin."""
        url = obj.image.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class _RecipeRefSerializer(serializers.Serializer):
    """The referenced recipe, as a card link."""

    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)


class _CourseRefSerializer(serializers.Serializer):
    """The referenced course, as a card link."""

    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)


class GalleryPostSerializer(serializers.Serializer):
    """A gallery post  the one shape for list and detail."""

    id = serializers.IntegerField(read_only=True)
    author_handle = serializers.CharField(read_only=True, source="author.username")
    author_display_name = serializers.SerializerMethodField()
    author_avatar_url = serializers.SerializerMethodField()
    caption = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    recipe = _RecipeRefSerializer(read_only=True, allow_null=True)
    course = _CourseRefSerializer(read_only=True, allow_null=True)
    images = GalleryImageSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_author_display_name(self, obj: Any) -> str:
        """Return the author's display name, falling back to the handle."""
        profile = getattr(obj.author, "profile", None)
        return (profile.display_name if profile else "") or obj.author.username

    def get_author_avatar_url(self, obj: Any) -> str | None:
        """Return the author's absolute avatar URL, if any."""
        profile = getattr(obj.author, "profile", None)
        avatar = getattr(profile, "avatar", None) if profile else None
        if not avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(avatar.url) if request else avatar.url


class GalleryPostCreateSerializer(StrictSerializer):
    """Payload for creating a post."""

    caption = serializers.CharField(
        max_length=CAPTION_MAX_LENGTH, required=False, allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=GalleryPostStatus.choices, default=GalleryPostStatus.PUBLISHED
    )
    recipe_id = serializers.IntegerField(required=False, min_value=1)
    course_id = serializers.IntegerField(required=False, min_value=1)


class GalleryPostUpdateSerializer(StrictSerializer):
    """Payload for editing a post; absent keys are unchanged.

    ``image_ids`` reorders the gallery  it must be exactly the post's
    image-id set (the lessons reorder invariant), validated in the
    service. References may be cleared with ``null``.
    """

    caption = serializers.CharField(
        max_length=CAPTION_MAX_LENGTH, required=False, allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=GalleryPostStatus.choices, required=False
    )
    recipe_id = serializers.IntegerField(
        required=False, min_value=1, allow_null=True
    )
    course_id = serializers.IntegerField(
        required=False, min_value=1, allow_null=True
    )
    image_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        max_length=MAX_IMAGES_PER_POST,
    )


class GalleryImageUploadSerializer(StrictSerializer):
    """Multipart payload for one image upload."""

    image = serializers.ImageField()
