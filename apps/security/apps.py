"""App configuration for the security app."""

from __future__ import annotations

from django.apps import AppConfig


class SecurityConfig(AppConfig):
    """Threat watching  an observation sink with a small enforcement arm.

    A leaf app by construction. It imports no feature domain, holds no FK
    to any content, and nothing imports it back: the only way in is the
    middleware, which sees requests as (ip, path, method, user agent) and
    nothing more. That is what lets it sit at the edge of every request
    without coupling the platform to it.

    Its one hard rule is that watching must never break serving  every
    detector call site swallows and logs its own failures. See
    ``docs/adr/0025-threat-watch-and-client-guard.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.security"
    label = "security"
    verbose_name = "Security"
