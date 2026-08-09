"""App configuration for the recipes app."""

from __future__ import annotations

from django.apps import AppConfig


class RecipesConfig(AppConfig):
    """Recipes, their ingredients, steps, images and nutrition."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recipes"
    label = "recipes"
    verbose_name = "Recipes"
