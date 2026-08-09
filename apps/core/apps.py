"""App configuration for the core infrastructure app."""

from __future__ import annotations

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Project-wide base classes, middleware and context processors."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"
