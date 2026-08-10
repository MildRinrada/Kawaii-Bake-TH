"""Django admin for the security app.

Read-only by design. Events are evidence and profiles are derived from
them: the supported way to change a profile is the dashboard's block and
review actions, which record who did it. Editing rows here would leave no
such trace.
"""

from __future__ import annotations

from django.contrib import admin

from apps.security.models import SecurityEvent, ThreatProfile


class _ReadOnlyAdmin(admin.ModelAdmin):
    """Shared read-only posture."""

    def has_add_permission(self, request) -> bool:  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False


@admin.register(SecurityEvent)
class SecurityEventAdmin(_ReadOnlyAdmin):
    """Inspect recorded observations."""

    list_display = ("id", "created_at", "kind", "severity", "ip", "path", "status_code")
    list_filter = ("kind", "severity")
    search_fields = ("ip", "path", "user_agent")
    raw_id_fields = ("actor",)


@admin.register(ThreatProfile)
class ThreatProfileAdmin(_ReadOnlyAdmin):
    """Inspect offender summaries."""

    list_display = (
        "ip",
        "level",
        "score",
        "event_count",
        "last_seen_at",
        "blocked_until",
        "review_state",
    )
    list_filter = ("level", "review_state")
    search_fields = ("ip", "last_path", "last_user_agent")
    raw_id_fields = ("reviewed_by", "blocked_by")
