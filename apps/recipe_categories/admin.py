"""Django admin registration for recipe categories.

Categories are curated by staff here; the API exposes reads only.
"""

from __future__ import annotations

from django.contrib import admin

from apps.recipe_categories.models import RecipeCategory


@admin.register(RecipeCategory)
class RecipeCategoryAdmin(admin.ModelAdmin):
    """Admin for the category taxonomy."""

    list_display = ("name", "slug", "display_order", "is_active")
    list_filter = ("is_active",)
    list_editable = ("display_order", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")
