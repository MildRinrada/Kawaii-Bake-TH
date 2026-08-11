"""Django admin for the notifications app.

Notifications are private snapshots and preferences are the user's own
choices  both strictly read-only here (no admin CRUD, per the Phase 10
spec). Inspection only.
"""

from __future__ import annotations

from django.contrib import admin

from apps.notifications.models import (
    Notification,
    NotificationCampaign,
    NotificationPreference,
    NotificationTemplate,
)


class _ReadOnlyAdmin(admin.ModelAdmin):
    """Shared read-only posture."""

    def has_add_permission(self, request) -> bool:  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False


@admin.register(Notification)
class NotificationAdmin(_ReadOnlyAdmin):
    """Inspect delivered notifications."""

    list_display = ("id", "recipient", "event_type", "title", "read_at", "created_at")
    list_filter = ("event_type",)
    raw_id_fields = ("recipient",)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(_ReadOnlyAdmin):
    """Inspect explicit opt-outs."""

    list_display = ("user", "event_type", "enabled", "updated_at")
    list_filter = ("event_type", "enabled")
    raw_id_fields = ("user",)


@admin.register(NotificationCampaign)
class NotificationCampaignAdmin(_ReadOnlyAdmin):
    """Inspect staff campaigns - managed through the API surface."""

    list_display = (
        "id",
        "title",
        "kind",
        "status",
        "scheduled_at",
        "sent_at",
        "recipients_count",
        "created_by",
    )
    list_filter = ("status", "kind")
    raw_id_fields = ("created_by",)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(_ReadOnlyAdmin):
    """Inspect composer templates - managed through the API surface."""

    list_display = ("id", "name", "kind", "is_archived", "updated_at")
    list_filter = ("is_archived", "kind")
    raw_id_fields = ("created_by",)
