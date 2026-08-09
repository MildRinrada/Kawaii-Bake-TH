"""Django admin registration for recipes."""

from __future__ import annotations

from django.contrib import admin

from apps.recipes.models import (
    Nutrition,
    Recipe,
    RecipeImage,
    RecipeIngredient,
    RecipeStep,
)


class RecipeIngredientInline(admin.TabularInline):
    """Edit ingredient lines alongside the recipe."""

    model = RecipeIngredient
    extra = 0
    fields = ("position", "name", "quantity", "unit", "group", "is_optional")


class RecipeStepInline(admin.TabularInline):
    """Edit steps alongside the recipe."""

    model = RecipeStep
    extra = 0
    fields = ("position", "body", "duration_minutes")


class RecipeImageInline(admin.TabularInline):
    """Edit gallery images alongside the recipe."""

    model = RecipeImage
    extra = 0
    fields = ("position", "image", "caption")


class NutritionInline(admin.StackedInline):
    """Edit nutrition alongside the recipe."""

    model = Nutrition
    extra = 0
    can_delete = True


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Admin for recipes."""

    inlines = (RecipeIngredientInline, RecipeStepInline, RecipeImageInline, NutritionInline)

    list_display = ("title", "author", "status", "visibility", "published_at")
    list_filter = ("status", "visibility", "difficulty", "categories")
    search_fields = ("title", "slug", "author__username", "author__email")
    autocomplete_fields = ("author",)
    filter_horizontal = ("categories",)
    readonly_fields = ("total_minutes", "created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("author", "title", "slug", "summary", "description")}),
        ("Classification", {"fields": ("categories", "difficulty")}),
        (
            "Timing",
            {"fields": ("prep_minutes", "cook_minutes", "total_minutes", "servings")},
        ),
        ("Publication", {"fields": ("status", "visibility", "published_at")}),
        ("Media", {"fields": ("cover_image",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
