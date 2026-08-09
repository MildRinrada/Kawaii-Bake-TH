"""Django admin registration for favorites."""

from __future__ import annotations

from django.contrib import admin

from apps.favorites.models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Admin for favorites — read-only rows."""

    list_display = ("id", "user", "target_kind", "recipe", "course", "created_at")
    search_fields = ("user__username", "recipe__title", "course__title")
    autocomplete_fields = ("user", "recipe", "course")
    readonly_fields = ("user", "recipe", "course", "created_at", "updated_at")
