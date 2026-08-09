"""Test data builders for the gallery domain."""

from __future__ import annotations

import io
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.gallery.constants import GalleryPostStatus
from apps.gallery.models import GalleryPost


def create_post(
    *,
    author: Any,
    caption: str = "อบเสร็จใหม่ ๆ 🧁",
    status: str = GalleryPostStatus.PUBLISHED,
    **extra: Any,
) -> GalleryPost:
    """Create a gallery post directly at the model layer."""
    return GalleryPost.objects.create(
        author=author, caption=caption, status=status, **extra
    )


def make_image_file(
    *, name: str = "bake.png", image_format: str = "PNG"
) -> SimpleUploadedFile:
    """Build a real, decodable image upload."""
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="pink").save(buffer, format=image_format)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")
