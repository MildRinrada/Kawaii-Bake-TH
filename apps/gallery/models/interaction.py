"""Gallery interactions: likes and comments (ADR 0032)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.gallery.constants import COMMENT_BODY_MAX_LENGTH


class GalleryLike(models.Model):
    """One account's like on one post.

    A row *is* the like: there is no counter to drift, the count is
    always ``COUNT(*)`` over these rows (the standing no-counters rule
    that ``GalleryPost`` already documents). The unique constraint makes
    liking idempotent at the database level, so a double-tap race ends
    as one like rather than two.

    Deleting the post or the account removes the like with it - a like
    is meaningless without both sides, and nothing references it.
    """

    post = models.ForeignKey(
        "gallery.GalleryPost", on_delete=models.CASCADE, related_name="likes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gallery_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "gallery like"
        verbose_name_plural = "gallery likes"
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"], name="gallery_like_unique"
            ),
        ]

    def __str__(self) -> str:
        """Return the like description."""
        return f"like {self.pk} · post {self.post_id}"


class GalleryComment(TimeStampedModel):
    """One account's comment on one post.

    Comments are leaves - nothing references them - so deletion is hard,
    exactly like a Q&A answer. They are reachable only through their
    post's visibility: hiding the post takes its comments off every API
    surface with it, so no separate moderation state is needed here.
    """

    post = models.ForeignKey(
        "gallery.GalleryPost", on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gallery_comments",
    )
    body = models.TextField(max_length=COMMENT_BODY_MAX_LENGTH)

    class Meta:
        verbose_name = "gallery comment"
        verbose_name_plural = "gallery comments"
        # Chronological - a conversation reads top to bottom.
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=["post", "created_at"], name="gallery_comment_post_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the comment description."""
        return f"comment {self.pk} · post {self.post_id}"
