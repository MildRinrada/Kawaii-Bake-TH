"""Business logic for gallery likes and comments (ADR 0032).

Every write here goes through the *visible* post selector first: a post
the caller cannot see cannot be liked or commented on, and the refusal is
the same 404 the rest of the app gives. Counts are never stored - the
read side aggregates rows live.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction

from apps.gallery.exceptions import (
    GalleryCommentNotFoundError,
    GalleryPostNotFoundError,
)
from apps.gallery.models import GalleryComment, GalleryLike, GalleryPost
from apps.notifications.services import notification_service

logger = logging.getLogger("kawaiibake.gallery")


def _visible_post(*, post_id: int, viewer_id: int, viewer_is_staff: bool) -> GalleryPost:
    """Return a post the caller may interact with, or raise 404."""
    # Imported here: the selector imports models, and the service is the
    # only caller that needs both directions.
    from apps.gallery.selectors import gallery_selector

    post = gallery_selector.get_post(
        post_id=post_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if post is None:
        raise GalleryPostNotFoundError
    return post


def like_post(*, post_id: int, user_id: int, viewer_is_staff: bool = False) -> bool:
    """Like a post on the caller's behalf, idempotently.

    Args:
        post_id: Primary key of the post.
        user_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        ``True`` when this call created the like, ``False`` when it
        already existed.

    Raises:
        GalleryPostNotFoundError: If the post is absent or hidden.
    """
    post = _visible_post(
        post_id=post_id, viewer_id=user_id, viewer_is_staff=viewer_is_staff
    )
    try:
        # The unique constraint - not a read-then-write - decides the
        # race: two taps in flight end as one like.
        with transaction.atomic():
            GalleryLike.objects.create(post=post, user_id=user_id)
    except IntegrityError:
        return False
    return True


def unlike_post(*, post_id: int, user_id: int, viewer_is_staff: bool = False) -> None:
    """Remove the caller's like, if any (idempotent).

    Args:
        post_id: Primary key of the post.
        user_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        GalleryPostNotFoundError: If the post is absent or hidden.
    """
    post = _visible_post(
        post_id=post_id, viewer_id=user_id, viewer_is_staff=viewer_is_staff
    )
    GalleryLike.objects.filter(post=post, user_id=user_id).delete()


def add_comment(
    *, post_id: int, author_id: int, body: str, viewer_is_staff: bool = False
) -> GalleryComment:
    """Post a comment and tell the post's author about it.

    Args:
        post_id: Primary key of the post.
        author_id: Primary key of the commenter.
        body: The validated comment text.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The created comment, author preloaded.

    Raises:
        GalleryPostNotFoundError: If the post is absent or hidden.
    """
    post = _visible_post(
        post_id=post_id, viewer_id=author_id, viewer_is_staff=viewer_is_staff
    )
    comment = GalleryComment.objects.create(
        post=post, author_id=author_id, body=body.strip()
    )
    if post.author_id != author_id:
        # Never notify yourself - the same rule Q&A answers follow.
        notification_service.notify_gallery_comment(
            post_author_id=post.author_id,
            commenter_handle=comment.author.username,
            post_id=post.id,
            excerpt=comment.body[:60],
        )
    return GalleryComment.objects.select_related("author", "author__profile").get(
        pk=comment.pk
    )


def delete_comment(
    *, comment_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Delete a comment.

    Removable by its author, by the owner of the post it sits on (your
    wall, your call), or by staff. Anyone else gets the same 404 an
    absent comment gives.

    Args:
        comment_id: Primary key of the comment.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        GalleryCommentNotFoundError: If absent or not the caller's to remove.
    """
    comment = (
        GalleryComment.objects.select_related("post").filter(pk=comment_id).first()
    )
    if comment is None:
        raise GalleryCommentNotFoundError
    allowed = (
        viewer_is_staff
        or comment.author_id == viewer_id
        or comment.post.author_id == viewer_id
    )
    if not allowed:
        raise GalleryCommentNotFoundError
    comment.delete()
