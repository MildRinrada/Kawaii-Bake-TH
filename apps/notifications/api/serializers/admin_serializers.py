"""Serializers for the staff notifications surface."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import (
    PaginatedFilterSerializer,
    StrictSerializer,
)
from apps.notifications.constants import (
    CAMPAIGN_BODY_MAX_LENGTH,
    CAMPAIGN_TITLE_MAX_LENGTH,
    CTA_MAX_LENGTH,
    LINK_MAX_LENGTH,
    TEMPLATE_NAME_MAX_LENGTH,
    AnnouncementKind,
    CampaignStatus,
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

    title = serializers.CharField(max_length=CAMPAIGN_TITLE_MAX_LENGTH)
    body = serializers.CharField(
        max_length=CAMPAIGN_BODY_MAX_LENGTH, required=False, allow_blank=True
    )
    # An announcement with nowhere to go is a notification the reader can
    # do nothing about, so the destination is not optional.
    link = serializers.CharField(max_length=LINK_MAX_LENGTH)


class BroadcastResultSerializer(serializers.Serializer):
    """How far a broadcast reached."""

    recipients = serializers.IntegerField(read_only=True)


# --------------------------------------------------------------------------
# Campaigns and templates (ADR 0030)
# --------------------------------------------------------------------------


class CampaignSerializer(serializers.Serializer):
    """One staff campaign row, author and read receipts included."""

    id = serializers.IntegerField(read_only=True)
    kind = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    cta_text = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    audience = serializers.JSONField(read_only=True)
    status = serializers.CharField(read_only=True)
    scheduled_at = serializers.DateTimeField(read_only=True, allow_null=True)
    sent_at = serializers.DateTimeField(read_only=True, allow_null=True)
    recipients_count = serializers.IntegerField(
        read_only=True, allow_null=True
    )
    read_count = serializers.IntegerField(read_only=True, default=0)
    click_count = serializers.IntegerField(read_only=True, default=0)
    created_by = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_created_by(self, obj: Any) -> str:
        """Return the author's handle, blank when the account is gone."""
        return obj.created_by.username if obj.created_by else ""


class CampaignWriteSerializer(StrictSerializer):
    """Payload for creating or editing a campaign.

    ``audience`` is passed through as JSON - the service's audience
    validator closes its schema (kinds, params, ranges), so the API
    layer does not duplicate that contract.
    """

    # A closed set, not a slug: the kind picks the glyph and colour the
    # recipient sees, so a value the client cannot draw is not a value.
    kind = serializers.ChoiceField(
        choices=AnnouncementKind.choices,
        required=False,
        default=AnnouncementKind.GENERAL,
    )
    title = serializers.CharField(max_length=CAMPAIGN_TITLE_MAX_LENGTH)
    body = serializers.CharField(
        max_length=CAMPAIGN_BODY_MAX_LENGTH, required=False, allow_blank=True
    )
    cta_text = serializers.CharField(
        max_length=CTA_MAX_LENGTH, required=False, allow_blank=True
    )
    # Required for the same reason as a broadcast's: see above.
    link = serializers.CharField(max_length=LINK_MAX_LENGTH)
    audience = serializers.JSONField()
    status = serializers.ChoiceField(
        choices=(CampaignStatus.DRAFT, CampaignStatus.SCHEDULED),
        required=False,
        default=CampaignStatus.DRAFT,
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)


class CampaignFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the campaign list."""

    status = serializers.ChoiceField(
        choices=CampaignStatus.choices, required=False, allow_blank=True
    )
    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )


class CampaignAnalyticsSerializer(serializers.Serializer):
    """Honest delivery analytics: snapshots created and read receipts."""

    recipients = serializers.IntegerField(read_only=True)
    delivered = serializers.IntegerField(read_only=True)
    read = serializers.IntegerField(read_only=True)
    unread = serializers.IntegerField(read_only=True)
    read_rate = serializers.FloatField(read_only=True)
    # Reported by the recipient's browser, so a floor rather than a
    # measurement - the panel labels it as one.
    clicked = serializers.IntegerField(read_only=True)
    click_rate = serializers.FloatField(read_only=True)
    sent_at = serializers.DateTimeField(read_only=True, allow_null=True)


class AudienceEstimateSerializer(StrictSerializer):
    """Payload for a recipient-count estimate."""

    audience = serializers.JSONField()


class AudienceEstimateResultSerializer(serializers.Serializer):
    """How many accounts the audience resolves to right now."""

    count = serializers.IntegerField(read_only=True)


class TemplateItemSerializer(serializers.Serializer):
    """One reusable composer template."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    kind = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    cta_text = serializers.CharField(read_only=True)
    link = serializers.CharField(read_only=True)
    is_archived = serializers.BooleanField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class TemplateWriteSerializer(StrictSerializer):
    """Payload for creating or editing a template."""

    name = serializers.CharField(max_length=TEMPLATE_NAME_MAX_LENGTH)
    kind = serializers.ChoiceField(
        choices=AnnouncementKind.choices,
        required=False,
        default=AnnouncementKind.GENERAL,
    )
    title = serializers.CharField(max_length=CAMPAIGN_TITLE_MAX_LENGTH)
    body = serializers.CharField(
        max_length=CAMPAIGN_BODY_MAX_LENGTH, required=False, allow_blank=True
    )
    cta_text = serializers.CharField(
        max_length=CTA_MAX_LENGTH, required=False, allow_blank=True
    )
    link = serializers.CharField(
        max_length=LINK_MAX_LENGTH, required=False, allow_blank=True
    )
    is_archived = serializers.BooleanField(required=False)


class AdminNotificationStatsSerializer(serializers.Serializer):
    """Headline numbers for the staff notifications hub."""

    campaigns_sent = serializers.IntegerField(read_only=True)
    drafts = serializers.IntegerField(read_only=True)
    scheduled = serializers.IntegerField(read_only=True)
    sent_today = serializers.IntegerField(read_only=True)
    delivered_total = serializers.IntegerField(read_only=True)
    read_total = serializers.IntegerField(read_only=True)
    clicked_total = serializers.IntegerField(read_only=True)
