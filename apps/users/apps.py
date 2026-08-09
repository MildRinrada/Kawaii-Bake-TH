"""App configuration for the users app."""

from __future__ import annotations

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Custom user model, profiles and preferences."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    label = "users"
    verbose_name = "Users"
