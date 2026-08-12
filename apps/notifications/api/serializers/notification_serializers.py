"""Serializers for notification payloads."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer


class NotificationSerializer(serializers.Serializer):
    """One notification row  the snapshot, verbatim."""

    id = serializers.IntegerField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    actor_handle = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    # ADR 0030: campaign sends carry the announcement kind and a CTA
    # label; machine events leave both blank and the frontend draws them
    # from `event_type`. The kind is what picks the glyph and colour -
    # the sender chooses a category, the design system chooses the
    # picture.
    kind = serializers.CharField(read_only=True)
    cta_text = serializers.CharField(read_only=True)
    read_at = serializers.DateTimeField(read_only=True, allow_null=True)
    clicked_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class NotificationListSerializer(serializers.Serializer):
    """Schema shape of the list endpoint (docs only).

    The view assembles this by hand: the standard paginated envelope plus
    the live ``unread_count``.
    """

    count = serializers.IntegerField(read_only=True)
    next = serializers.CharField(read_only=True, allow_null=True)
    previous = serializers.CharField(read_only=True, allow_null=True)
    unread_count = serializers.IntegerField(read_only=True)
    results = NotificationSerializer(many=True, read_only=True)


class NotificationPreferencesSerializer(StrictSerializer):
    """The per-event preference map  GET response and PATCH request.

    One declared boolean per supported event type; ``StrictSerializer``
    rejects unknown event types (and any other stray key) loudly. All
    fields optional on PATCH  absent means unchanged.
    """

    review_received = serializers.BooleanField(required=False)
    course_enrollment = serializers.BooleanField(required=False)
    achievement_earned = serializers.BooleanField(required=False)
    qa_answer_received = serializers.BooleanField(required=False)
    qa_answer_accepted = serializers.BooleanField(required=False)
    gallery_comment = serializers.BooleanField(required=False)
    announcement = serializers.BooleanField(required=False)


class ReadAllResultSerializer(serializers.Serializer):
    """Result of the bulk read stamp."""

    marked_read = serializers.IntegerField(read_only=True)
