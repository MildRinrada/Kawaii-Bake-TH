"""App configuration for the authentication app."""

from __future__ import annotations

from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    """Registration, sign-in, password reset and email verification."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authentication"
    label = "authentication"
    verbose_name = "Authentication"

    def ready(self) -> None:
        """Register the OpenAPI authentication extension."""
        from apps.authentication.api import schema  # noqa: F401
