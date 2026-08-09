"""App configuration for shared, domain-agnostic helpers."""

from __future__ import annotations

from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Reusable mixins, template tags, widgets and utilities."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    label = "common"
    verbose_name = "Common"
