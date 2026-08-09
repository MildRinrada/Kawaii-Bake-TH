"""App configuration for the favorites app."""

from __future__ import annotations

from django.apps import AppConfig


class FavoritesConfig(AppConfig):
    """User bookmarks of recipes and courses.

    Same target architecture as reviews (explicit nullable FKs, exactly one
    set — ADR 0011). A favorite is a lightweight toggle: rows are hard-deleted
    on unfavorite; longitudinal history belongs to a future analytics event
    stream, not to soft-deleted toggle rows.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.favorites"
    label = "favorites"
    verbose_name = "Favorites"
