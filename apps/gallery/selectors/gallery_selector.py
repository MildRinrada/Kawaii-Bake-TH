"""Read-side queries for gallery posts."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from apps.gallery.models import GalleryImage, GalleryPost
from apps.gallery.selectors.gallery_visibility import visible_q


def _base_queryset() -> QuerySet[GalleryPost]:
    """The shape every read shares: author, references and ordered images."""
    return GalleryPost.objects.select_related(
        "author", "recipe", "course"
    ).prefetch_related(
        Prefetch(
            "images", queryset=GalleryImage.objects.order_by("position", "id")
        )
    )


def list_posts(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    recipe_id: int | None = None,
    course_id: int | None = None,
    category_slug: str | None = None,
    author_username: str | None = None,
) -> QuerySet[GalleryPost]:
    """The gallery feed for a viewer, newest first.

    Filters only narrow the visibility-restricted set — they can never
    widen it.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        recipe_id: Restrict to posts of one recipe.
        course_id: Restrict to posts of one course.
        category_slug: Restrict to posts whose recipe is in a category.
        author_username: Restrict to one author's posts.

    Returns:
        A lazy queryset.
    """
    queryset = _base_queryset().filter(
        visible_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
    )
    if recipe_id is not None:
        queryset = queryset.filter(recipe_id=recipe_id)
    if course_id is not None:
        queryset = queryset.filter(course_id=course_id)
    if category_slug:
        queryset = queryset.filter(
            recipe__categories__slug=category_slug
        ).distinct()
    if author_username:
        queryset = queryset.filter(author__username__iexact=author_username)
    return queryset


def get_post(
    *, post_id: int, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> GalleryPost | None:
    """Fetch one post under the same rule as the list.

    Args:
        post_id: Primary key of the post.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The post, or ``None`` when absent or hidden.
    """
    return (
        _base_queryset()
        .filter(visible_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff))
        .filter(pk=post_id)
        .first()
    )


def get_editable_post(
    *, post_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> GalleryPost | None:
    """Fetch a post the caller may mutate — author or staff, nothing else.

    Args:
        post_id: Primary key of the post.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The post, or ``None``.
    """
    queryset = GalleryPost.objects.filter(pk=post_id)
    if not viewer_is_staff:
        queryset = queryset.filter(author_id=viewer_id)
    return queryset.first()
