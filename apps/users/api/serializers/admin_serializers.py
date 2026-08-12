"""Serializers for the staff user roster.

These shapes carry PII (email, legal name) by design: they are rendered
only by ``IsAdminUser``-gated views. Nothing here is ever reachable from
a public endpoint.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import (
    PaginatedFilterSerializer,
    StrictSerializer,
)
from apps.users.constants import NAME_PART_MAX_LENGTH


class AdminUserSerializer(serializers.Serializer):
    """One account row on the staff roster."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    experience_level = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)
    email_verified_at = serializers.DateTimeField(read_only=True, allow_null=True)
    terms_accepted_at = serializers.DateTimeField(read_only=True, allow_null=True)
    deactivated_at = serializers.DateTimeField(read_only=True, allow_null=True)
    last_login = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    # Activity annotations (selector `_with_activity`) - real counts, so
    # the roster can say "เรียน 4 คอร์ส · สูตร 12" without N+1 calls.
    recipes_count = serializers.IntegerField(read_only=True, default=0)
    courses_count = serializers.IntegerField(read_only=True, default=0)
    posts_count = serializers.IntegerField(read_only=True, default=0)

    def get_display_name(self, obj: Any) -> str:
        """Return the profile display name, falling back to the handle."""
        profile = getattr(obj, "profile", None)
        return (profile.display_name if profile else "") or obj.username

    def get_avatar_url(self, obj: Any) -> str | None:
        """Return the absolute avatar URL, or ``None`` when unset."""
        profile = getattr(obj, "profile", None)
        avatar = getattr(profile, "avatar", None) if profile else None
        if not avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(avatar.url) if request else avatar.url

    def get_experience_level(self, obj: Any) -> str:
        """Return the self-declared skill level from the profile."""
        profile = getattr(obj, "profile", None)
        return profile.experience_level if profile else ""


class AdminUserUpdateSerializer(StrictSerializer):
    """Staff edit payload; absent keys are unchanged."""

    first_name = serializers.CharField(
        max_length=NAME_PART_MAX_LENGTH, required=False, allow_blank=True
    )
    last_name = serializers.CharField(
        max_length=NAME_PART_MAX_LENGTH, required=False, allow_blank=True
    )
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    is_email_verified = serializers.BooleanField(required=False)


class AdminUserStatsSerializer(serializers.Serializer):
    """Headline account numbers for the roster's summary cards."""

    total = serializers.IntegerField(read_only=True)
    active = serializers.IntegerField(read_only=True)
    pending = serializers.IntegerField(read_only=True)
    suspended = serializers.IntegerField(read_only=True)
    staff = serializers.IntegerField(read_only=True)
    new_7d = serializers.IntegerField(read_only=True)


class AdminUserFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the roster listing."""

    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=("active", "suspended"), required=False, allow_blank=True
    )
    verified = serializers.BooleanField(required=False, allow_null=True)
    staff = serializers.BooleanField(required=False, allow_null=True)
    joined_days = serializers.IntegerField(
        required=False, min_value=1, max_value=365
    )
    ordering = serializers.ChoiceField(
        choices=("newest", "oldest", "username", "recently_active"),
        required=False,
        allow_blank=True,
    )
