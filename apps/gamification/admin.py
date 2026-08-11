"""Django admin for the gamification app.

The ledger is append-only and the level/streak rows are derived  all
three are read-only here. Repairs go through recalculation, never field
edits.
"""

from __future__ import annotations

from django.contrib import admin

from apps.gamification.models import DailyStreak, UserLevel, XPTransaction


class _ReadOnlyAdmin(admin.ModelAdmin):
    """Shared read-only posture for derived and append-only tables."""

    def has_add_permission(self, request) -> bool:  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False


@admin.register(XPTransaction)
class XPTransactionAdmin(_ReadOnlyAdmin):
    """Inspect the XP ledger."""

    list_display = ("id", "user", "reason", "points", "created_at")
    list_filter = ("reason",)
    raw_id_fields = ("user",)


@admin.register(UserLevel)
class UserLevelAdmin(_ReadOnlyAdmin):
    """Inspect derived levels."""

    list_display = ("user", "current_level", "current_xp", "total_xp", "updated_at")
    raw_id_fields = ("user",)


@admin.register(DailyStreak)
class DailyStreakAdmin(_ReadOnlyAdmin):
    """Inspect derived streaks."""

    list_display = (
        "user",
        "current_streak",
        "longest_streak",
        "last_activity_date",
        "updated_at",
    )
    raw_id_fields = ("user",)
