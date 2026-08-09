"""App configuration for the certificates app."""

from __future__ import annotations

from django.apps import AppConfig


class CertificatesConfig(AppConfig):
    """Course certificates, achievements and the badge foundation.

    Owns issuance state and nothing else: completion is **read** from the
    progress app's public selectors (certificates never calculate it), the
    course is resolved through courses' public refs, and no content app
    imports this one. Not gamification — no XP, levels, streaks or
    leaderboards live here. See ``docs/adr/0014-certificates-and-achievements.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.certificates"
    label = "certificates"
    verbose_name = "Certificates"
