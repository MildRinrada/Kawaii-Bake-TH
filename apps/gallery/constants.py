"""Enumerations and magic values for the gallery app."""

from __future__ import annotations

from django.db import models


class GalleryPostStatus(models.TextChoices):
    """Lifecycle of a gallery post.

    Two states only: a showcase photo is either shared or it is not.
    There is no "deleted" state  deletion is hard, with media cleanup,
    because nothing historical ever references a gallery post.
    """

    PUBLISHED = "published", "Published"
    UNPUBLISHED = "unpublished", "Unpublished"


CAPTION_MAX_LENGTH = 500

# A comment is a reaction, not an essay - the same ceiling reviews use.
COMMENT_BODY_MAX_LENGTH = 1000

MAX_IMAGES_PER_POST = 10
GALLERY_IMAGE_UPLOAD_DIR = "gallery"
GALLERY_IMAGE_MAX_SIZE_BYTES = 5 * 1024 * 1024
# SVG is excluded everywhere in the project  it can carry script.
ALLOWED_GALLERY_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
ALLOWED_GALLERY_IMAGE_FORMATS = ("JPEG", "PNG", "WEBP")
