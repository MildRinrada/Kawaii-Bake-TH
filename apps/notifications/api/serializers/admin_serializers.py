"""Serializers for the staff notifications surface."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import (
    PaginatedFilterSerializer,
    StrictSerializer,
)
from apps.notifications.constants import (
    BODY_MAX_LENGTH,
    LINK_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    NotificationEventType,
)


class AdminNotificationSerializer(serializers.Serializer):
    """One delivered notification, recipient included."""

    id = serializers.IntegerField(read_only=True)
    recipient = serializers.CharField(read_only=True, source="recipient.username")
    recipient_display_name = serializers.SerializerMethodField()
    event_type = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    actor_handle = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    read_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)

    def get_recipient_display_name(self, obj: Any) -> str:
        """Return the recipient's display name, falling back to the handle."""
        profile = getattr(obj.recipient, "profile", None)
        return (profile.display_name if profile else "") or obj.recipient.username


class AdminNotificationFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the cross-user notification list."""

    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    event_type = serializers.ChoiceField(
        choices=NotificationEventType.choices, required=False, allow_blank=True
    )
    unread = serializers.BooleanField(required=False, allow_null=True)


class BroadcastSerializer(StrictSerializer):
    """Payload for a platform announcement."""

    title = serializers.CharField(max_length=TITLE_MAX_LENGTH)
    body = serializers.CharField(
        max_length=BODY_MAX_LENGTH, required=False, allow_blank=True
    )
    link = serializers.CharField(
        max_length=LINK_MAX_LENGTH, required=False, allow_blank=True
    )


class BroadcastResultSerializer(serializers.Serializer):
    """How far a broadcast reached."""

    recipients = serializers.IntegerField(read_only=True)
