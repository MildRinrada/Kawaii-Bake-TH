"""App configuration for the gallery app."""

from __future__ import annotations

from django.apps import AppConfig


class GalleryConfig(AppConfig):
    """User-generated showcase posts  "I baked this".

    A community domain on the dependent side toward recipes and courses:
    posts reference content through nullable ``SET_NULL`` FKs, content
    apps know nothing of the gallery, and the reference must be publicly
    visible at creation. Posts are hard-deleted with real media cleanup 
    nothing historical references them. No follows, feeds, hashtags or
    moderation dashboard in this phase.
    See ``docs/adr/0017-community-gallery-and-qa.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.gallery"
    label = "gallery"
    verbose_name = "Gallery"
