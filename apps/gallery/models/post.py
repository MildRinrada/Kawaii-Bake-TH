"""The gallery post entity."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.gallery.constants import CAPTION_MAX_LENGTH, GalleryPostStatus


class GalleryPost(TimeStampedModel):
    """One user's "I baked this" showcase.

    Content references are nullable ``SET_NULL`` FKs (the assistant
    precedent, ADR 0013): deleting a recipe must not delete anyone's
    showcase, so the post degrades to reference-free instead. Both may be
    null  a free-standing bake is a valid post. The reference must be
    **publicly visible at creation** (service rule): the post itself is
    public, so its card may only ever name content the public could open.

    No like/comment/view counters  interactions are a future phase, and
    when they arrive they will aggregate live (the standing no-counters
    rule).
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gallery_posts",
    )
    caption = models.TextField(max_length=CAPTION_MAX_LENGTH, blank=True)
    status = models.CharField(
        max_length=20,
        choices=GalleryPostStatus.choices,
        default=GalleryPostStatus.PUBLISHED,
        db_index=True,
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.SET_NULL,
        related_name="gallery_posts",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        related_name="gallery_posts",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "gallery post"
        verbose_name_plural = "gallery posts"
        ordering = ("-created_at", "-id")
        indexes = [
            # The public feed: published, newest first.
            models.Index(
                fields=["status", "-created_at"], name="gallery_feed_idx"
            ),
            # A user's own wall.
            models.Index(
                fields=["author", "-created_at"], name="gallery_author_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the post description."""
        return f"gallery post {self.pk} · user {self.author_id}"
