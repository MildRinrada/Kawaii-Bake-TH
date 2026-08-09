"""Django admin registration for reviews — the moderation surface."""

from __future__ import annotations

from django.contrib import admin

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin for reviews. Content fields are read-only; status is the lever."""

    list_display = (
        "id",
        "user",
        "target_kind",
        "recipe",
        "course",
        "rating",
        "status",
        "created_at",
    )
    list_filter = ("status", "rating")
    search_fields = ("comment", "user__username", "recipe__title", "course__title")
    autocomplete_fields = ("user", "recipe", "course")
    readonly_fields = ("user", "recipe", "course", "rating", "comment", "created_at", "updated_at")
