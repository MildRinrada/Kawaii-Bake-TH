"""Write operations for gallery posts and images.

A repository is justified here for one reason: rows and stored files must
never drift apart. Django deletes no files on row deletion, so every
destructive path below removes the file explicitly.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max

from apps.gallery.models import GalleryImage, GalleryPost


def create_post(
    *,
    author_id: int,
    caption: str,
    status: str,
    recipe_id: int | None,
    course_id: int | None,
) -> GalleryPost:
    """Create a post row.

    Args:
        author_id: Primary key of the author.
        caption: The caption text.
        status: A value of :class:`GalleryPostStatus`.
        recipe_id: Optional referenced recipe.
        course_id: Optional referenced course.

    Returns:
        The saved post.
    """
    return GalleryPost.objects.create(
        author_id=author_id,
        caption=caption,
        status=status,
        recipe_id=recipe_id,
        course_id=course_id,
    )


def add_image(*, post: GalleryPost, image: Any) -> GalleryImage:
    """Append an image at the end of the post's gallery.

    Args:
        post: The owning post.
        image: The validated uploaded file.

    Returns:
        The created image.
    """
    highest = (
        GalleryImage.objects.filter(post=post).aggregate(Max("position"))[
            "position__max"
        ]
        or 0
    )
    return GalleryImage.objects.create(
        post=post, image=image, position=highest + 1
    )


def delete_image(*, image: GalleryImage) -> None:
    """Delete one image row and its stored file.

    Args:
        image: The image to delete.
    """
    stored = image.image
    image.delete()
    if stored:
        stored.delete(save=False)


def reorder_images(*, post: GalleryPost, ordered_ids: list[int]) -> None:
    """Renumber the post's images to match ``ordered_ids``.

    The caller has already validated the id set; positions become dense
    1..n in one ``bulk_update``.

    Args:
        post: The owning post.
        ordered_ids: Every image id of the post, in the desired order.
    """
    rows = {row.pk: row for row in GalleryImage.objects.filter(post=post)}
    for index, image_id in enumerate(ordered_ids, start=1):
        rows[image_id].position = index
    GalleryImage.objects.bulk_update(rows.values(), ["position"])


def delete_post(*, post: GalleryPost) -> None:
    """Hard-delete a post, its image rows and their stored files.

    Files are collected before the row cascade and removed after the
    database commit — a failed transaction must not have half-deleted
    media, and a committed one must not leave orphans.

    Args:
        post: The post to delete.
    """
    stored_files = [row.image for row in post.images.all() if row.image]
    with transaction.atomic():
        post.delete()
    for stored in stored_files:
        stored.delete(save=False)
