"""Business logic for gallery posts and their images."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from apps.courses.selectors import course_selector
from apps.gallery.exceptions import (
    GalleryPostNotFoundError,
    InvalidGalleryReferenceError,
    InvalidImageOrderError,
)
from apps.gallery.models import GalleryImage, GalleryPost
from apps.gallery.repositories import gallery_repository
from apps.gallery.selectors import gallery_selector
from apps.gallery.validators.gallery_validator import (
    validate_capacity,
    validate_gallery_image,
)
from apps.recipes.selectors import recipe_selector

logger = logging.getLogger("kawaiibake.gallery")


def create_post(
    *, author_id: int, data: Mapping[str, Any]
) -> GalleryPost:
    """Create a post, validating any content references.

    Args:
        author_id: Primary key of the author.
        data: Validated payload (caption, status, recipe_id, course_id).

    Returns:
        The created post, relations preloaded.

    Raises:
        InvalidGalleryReferenceError: If a reference is not public.
    """
    _validate_references(
        recipe_id=data.get("recipe_id"), course_id=data.get("course_id")
    )
    post = gallery_repository.create_post(
        author_id=author_id,
        caption=(data.get("caption") or "").strip(),
        status=data["status"],
        recipe_id=data.get("recipe_id"),
        course_id=data.get("course_id"),
    )
    logger.info("gallery_post_created post_id=%s by=%s", post.pk, author_id)
    return _reload(post_id=post.pk, viewer_id=author_id)


def update_post(
    *,
    post_id: int,
    viewer_id: int,
    viewer_is_staff: bool = False,
    data: Mapping[str, Any],
) -> GalleryPost:
    """Edit caption/status/references, and optionally reorder images.

    Args:
        post_id: Primary key of the post.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload; absent keys are unchanged.

    Returns:
        The updated post.

    Raises:
        GalleryPostNotFoundError: If absent or not the caller's.
        InvalidGalleryReferenceError: If a new reference is not public.
        InvalidImageOrderError: If ``image_ids`` is not the exact set.
    """
    post = _require_editable(
        post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    if "recipe_id" in data or "course_id" in data:
        _validate_references(
            recipe_id=data.get("recipe_id", post.recipe_id),
            course_id=data.get("course_id", post.course_id),
        )

    updates: list[str] = []
    for field in ("caption", "status", "recipe_id", "course_id"):
        if field in data:
            setattr(post, field, data[field])
            updates.append(field)
    if updates:
        post.save(update_fields=[*updates, "updated_at"])

    if "image_ids" in data:
        _reorder(post=post, ordered_ids=data["image_ids"])

    return _reload(
        post_id=post.pk, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def delete_post(
    *, post_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Hard-delete a post with real media cleanup.

    Args:
        post_id: Primary key of the post.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        GalleryPostNotFoundError: If absent or not the caller's.
    """
    post = _require_editable(
        post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    gallery_repository.delete_post(post=post)
    logger.info("gallery_post_deleted post_id=%s by=%s", post_id, viewer_id)


def add_image(
    *, post_id: int, viewer_id: int, viewer_is_staff: bool = False, image: Any
) -> GalleryImage:
    """Attach one validated image to the caller's post.

    Validation happens before storage is touched, so a rejected upload
    leaves no file behind.

    Args:
        post_id: Primary key of the post.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        image: The uploaded file.

    Returns:
        The created image.

    Raises:
        GalleryPostNotFoundError: If absent or not the caller's.
        django.core.exceptions.ValidationError: If the file is
            unacceptable or the post is at capacity.
    """
    post = _require_editable(
        post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    validate_gallery_image(image)
    validate_capacity(current_count=post.images.count())
    return gallery_repository.add_image(post=post, image=image)


def remove_image(
    *,
    post_id: int,
    image_id: int,
    viewer_id: int,
    viewer_is_staff: bool = False,
) -> None:
    """Delete one image (row and file) from the caller's post.

    Args:
        post_id: Primary key of the post.
        image_id: Primary key of the image, scoped to the post.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        GalleryPostNotFoundError: If the post or image is absent, or the
            post is not the caller's.
    """
    post = _require_editable(
        post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    image = GalleryImage.objects.filter(post=post, pk=image_id).first()
    if image is None:
        raise GalleryPostNotFoundError("Image not found.")
    gallery_repository.delete_image(image=image)


def _reorder(*, post: GalleryPost, ordered_ids: list[int]) -> None:
    """Validate the exact-set invariant, then renumber."""
    current = set(
        GalleryImage.objects.filter(post=post).values_list("id", flat=True)
    )
    submitted = list(ordered_ids)
    if len(submitted) != len(set(submitted)) or set(submitted) != current:
        raise InvalidImageOrderError
    gallery_repository.reorder_images(post=post, ordered_ids=submitted)


def _validate_references(
    *, recipe_id: int | None, course_id: int | None
) -> None:
    """Require any referenced content to be publicly listed.

    Uses the content apps' **public listing rule** (not the author's own
    detail rule): the post is public, so its card may only name content
    an anonymous visitor could open.
    """
    if recipe_id is not None:
        if not recipe_selector.list_by_ids(ids=[recipe_id]).exists():
            raise InvalidGalleryReferenceError
    if course_id is not None:
        if not course_selector.list_viewable_by_ids(ids=[course_id]).exists():
            raise InvalidGalleryReferenceError


def _require_editable(
    *, post_id: int, viewer_id: int, viewer_is_staff: bool
) -> GalleryPost:
    """Fetch a post the caller may mutate; "not yours" is the same 404."""
    post = gallery_selector.get_editable_post(
        post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if post is None:
        raise GalleryPostNotFoundError
    return post


def _reload(
    *, post_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> GalleryPost:
    """Re-read with relations for serialization."""
    post = gallery_selector.get_post(
        post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if post is None:  # pragma: no cover - deleted between write and read
        raise GalleryPostNotFoundError
    return post
