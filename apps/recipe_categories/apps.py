"""App configuration for the recipe categories app."""

from __future__ import annotations

from django.apps import AppConfig


class RecipeCategoriesConfig(AppConfig):
    """Taxonomy shared by recipes and, later, courses."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recipe_categories"
    label = "recipe_categories"
    verbose_name = "Recipe categories"
