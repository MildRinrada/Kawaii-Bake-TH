"""Django admin for the notifications app.

Notifications are private snapshots and preferences are the user's own
choices — both strictly read-only here (no admin CRUD, per the Phase 10
spec). Inspection only.
"""

from __future__ import annotations

from django.contrib import admin

from apps.notifications.models import Notification, NotificationPreference


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
