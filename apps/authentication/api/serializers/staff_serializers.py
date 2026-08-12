"""Serializers for staff-initiated account actions (ADR 0031)."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.users.constants import NAME_PART_MAX_LENGTH, USERNAME_MAX_LENGTH


class AdminCreateUserSerializer(StrictSerializer):
    """Payload for creating an account on a member's behalf."""

    email = serializers.EmailField()
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH)
    password = serializers.CharField(write_only=True, max_length=128)
    first_name = serializers.CharField(
        max_length=NAME_PART_MAX_LENGTH, required=False, allow_blank=True
    )
    last_name = serializers.CharField(
        max_length=NAME_PART_MAX_LENGTH, required=False, allow_blank=True
    )
    verified = serializers.BooleanField(required=False, default=False)


class AdminCreatedUserSerializer(serializers.Serializer):
    """The created account, roster-shaped identity only."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)


class StaffActionResultSerializer(serializers.Serializer):
    """Result of a staff-triggered email action."""

    sent = serializers.BooleanField(read_only=True)
