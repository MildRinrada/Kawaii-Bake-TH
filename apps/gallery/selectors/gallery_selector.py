"""Read-side queries for gallery posts."""

from __future__ import annotations

from django.db.models import BooleanField, Count, Exists, OuterRef, Prefetch, QuerySet, Value

from apps.gallery.models import GalleryComment, GalleryImage, GalleryLike, GalleryPost
from apps.gallery.selectors.gallery_visibility import visible_q


def _base_queryset(viewer_id: int | None = None) -> QuerySet[GalleryPost]:
    """The shape every read shares: author, references, images, counts.

    Interaction counts are aggregated live (ADR 0032) - there is no
    stored counter to drift - and ``viewer_has_liked`` is an EXISTS
    subquery so the feed stays one query regardless of page size.
    """
    queryset = (
        GalleryPost.objects.select_related("author", "author__profile", "recipe", "course")
        .prefetch_related(
            Prefetch("images", queryset=GalleryImage.objects.order_by("position", "id"))
        )
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
        )
        # Aggregation drops the model's implicit ordering from the
        # GROUP BY query; state it so pagination stays stable.
        .order_by("-created_at", "-id")
    )
    if viewer_id is None:
        return queryset.annotate(viewer_has_liked=Value(False, output_field=BooleanField()))
    return queryset.annotate(
        viewer_has_liked=Exists(GalleryLike.objects.filter(post=OuterRef("pk"), user_id=viewer_id))
    )


def list_comments(*, post_id: int) -> QuerySet[GalleryComment]:
    """Comments under one post, oldest first.

    Visibility is the post's: callers resolve the post through
    :func:`get_post` first, so a hidden post's comments are unreachable.

    Args:
        post_id: Primary key of the post.

    Returns:
        A lazy queryset.
    """
    return GalleryComment.objects.select_related("author", "author__profile").filter(
        post_id=post_id
    )


def like_count(*, post_id: int) -> int:
    """Return the live like count for one post.

    Args:
        post_id: Primary key of the post.

    Returns:
        The number of likes.
    """
    return GalleryLike.objects.filter(post_id=post_id).count()


def list_posts(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    recipe_id: int | None = None,
    course_id: int | None = None,
    category_slug: str | None = None,
    author_username: str | None = None,
    post_status: str | None = None,
) -> QuerySet[GalleryPost]:
    """The gallery feed for a viewer, newest first.

    Filters only narrow the visibility-restricted set  they can never
    widen it: ``post_status`` intersects ``visible_q``, so a non-staff
    viewer asking for ``unpublished`` still sees only their own posts.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        recipe_id: Restrict to posts of one recipe.
        course_id: Restrict to posts of one course.
        category_slug: Restrict to posts whose recipe is in a category.
        author_username: Restrict to one author's posts.
        post_status: Restrict to one :class:`GalleryPostStatus`.

    Returns:
        A lazy queryset.
    """
    queryset = _base_queryset(viewer_id).filter(
        visible_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
    )
    if post_status:
        queryset = queryset.filter(status=post_status)
    if recipe_id is not None:
        queryset = queryset.filter(recipe_id=recipe_id)
    if course_id is not None:
        queryset = queryset.filter(course_id=course_id)
    if category_slug:
        queryset = queryset.filter(recipe__categories__slug=category_slug).distinct()
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
        _base_queryset(viewer_id)
        .filter(visible_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff))
        .filter(pk=post_id)
        .first()
    )


def get_editable_post(
    *, post_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> GalleryPost | None:
    """Fetch a post the caller may mutate  author or staff, nothing else.

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


def author_ids() -> list[int]:
    """User ids that have shared at least one community post.

    Part of the cross-app audience API (ADR 0030): campaign targeting
    reaches gallery authorship only through this selector. Ids only.

    Returns:
        The distinct post author ids.
    """
    return list(GalleryPost.objects.values_list("author_id", flat=True).distinct())
