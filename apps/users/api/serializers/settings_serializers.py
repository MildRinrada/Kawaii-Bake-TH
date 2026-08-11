"""Serializers for the read-only settings composition."""

from __future__ import annotations

from rest_framework import serializers

from apps.users.api.serializers.preference_serializers import (
    UserPreferenceSerializer,
)
from apps.users.api.serializers.profile_serializers import OwnProfileSerializer


class ProfileCompletionSerializer(serializers.Serializer):
    """The derived completion snapshot  computed, never stored."""

    completed = serializers.IntegerField(read_only=True)
    total = serializers.IntegerField(read_only=True)
    percent = serializers.IntegerField(read_only=True)
    missing = serializers.ListField(child=serializers.CharField(), read_only=True)


class MySettingsSerializer(serializers.Serializer):
    """Everything the settings screen needs, in one read.

    A pure composition (ADR 0020 §7): each block is serialized by (or
    read through) its owning domain  profile and preferences by users,
    the notification block from the notifications app's own effective-
    preferences selector. This endpoint owns nothing and writes nothing;
    every write still goes to the owner's endpoint.
    """

    profile = OwnProfileSerializer(read_only=True)
    preferences = UserPreferenceSerializer(read_only=True)
    notifications = serializers.DictField(
        child=serializers.BooleanField(), read_only=True
    )
    profile_completion = ProfileCompletionSerializer(read_only=True)
