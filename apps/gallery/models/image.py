"""Gallery post images."""

from __future__ import annotations

from django.db import models

from apps.common.utils.files import build_upload_path
from apps.core.models.base import TimeStampedModel
from apps.gallery.constants import GALLERY_IMAGE_UPLOAD_DIR
from infrastructure.storage import get_media_storage


def gallery_image_upload_to(instance: GalleryImage, filename: str) -> str:
    """Build the storage path for a gallery image."""
    return build_upload_path(
        directory=GALLERY_IMAGE_UPLOAD_DIR, filename=filename
    )


class GalleryImage(TimeStampedModel):
    """One photo on a gallery post.

    Ordering is ``(position, id)``  deterministic even mid-renumber.
    Rows never outlive their file: deletion goes through the repository,
    which removes the stored file explicitly (Django never does).
    """

    post = models.ForeignKey(
        "gallery.GalleryPost", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        upload_to=gallery_image_upload_to, storage=get_media_storage
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "gallery image"
        verbose_name_plural = "gallery images"
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=["post", "position"], name="gallery_image_order_idx"),
        ]

    def __str__(self) -> str:
        """Return the image description."""
        return f"image {self.pk} · post {self.post_id}"
