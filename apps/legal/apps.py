"""App configuration for the legal-documents domain."""

from __future__ import annotations

from django.apps import AppConfig


class LegalConfig(AppConfig):
    """Terms, privacy, PDPA and cookie documents, editable by staff."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.legal"
    label = "legal"
