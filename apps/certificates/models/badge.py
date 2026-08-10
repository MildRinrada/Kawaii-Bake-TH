"""The badge definition — system-owned display metadata."""

from __future__ import annotations

from django.db import models


class BadgeDefinition(models.Model):
    """How one achievement type is presented — bilingual, Thai first.

    System-owned: rows are seeded by migration and curated in Django admin;
    there is deliberately **no CRUD API**. Achievements reference a badge
    for display, but the earned fact lives on the achievement row itself —
    deactivating a badge hides future presentation without un-earning
    anything.
    """

    slug = models.SlugField(max_length=50, unique=True)
    title_th = models.CharField(max_length=100)
    title_en = models.CharField(max_length=100)
    description_th = models.CharField(max_length=255, blank=True)
    description_en = models.CharField(max_length=255, blank=True)
    # A frontend asset key (matches a file under `public/achievements/`),
    # never emoji or an uploaded image — the artwork itself is curated in
    # the frontend's static asset library, not here (see its README).
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "badge definition"
        verbose_name_plural = "badge definitions"
        ordering = ("slug",)

    def __str__(self) -> str:
        """Return the badge description."""
        return self.slug
