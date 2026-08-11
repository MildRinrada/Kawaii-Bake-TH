"""Business logic for reviews: create, edit, moderate, soft-delete."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from apps.courses.selectors import course_selector
from apps.notifications.services import notification_service
from apps.recipes.selectors import recipe_selector
from apps.reviews.constants import ReviewTargetKind
from apps.reviews.exceptions import (
    ModerationNotAllowedError,
    OwnContentReviewError,
    ReviewNotFoundError,
    ReviewTargetNotFoundError,
)
from apps.reviews.models import Review
from apps.reviews.permissions.review_permissions import can_edit_review, can_moderate
from apps.reviews.repositories import review_repository
from apps.reviews.selectors import review_selector
from apps.reviews.validators import review_validator

logger = logging.getLogger("kawaiibake.reviews")


def resolve_target(
    *,
    kind: str,
    slug: str,
    viewer_id: int | None,
    viewer_is_staff: bool = False,
) -> tuple[int, int, str]:
    """Resolve a target slug to ``(target_id, owner_id, title)`` through visibility.

    Goes through the content apps' public ref selectors, so hidden and absent
    are the same 404 and this app never touches another app's models. The
    title rides along for the notification snapshot (Phase 10).

    Args:
        kind: A value of :class:`ReviewTargetKind`.
        slug: The target's slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The target's primary key, its owner's primary key, and its title.

    Raises:
        ReviewTargetNotFoundError: If the target is absent or hidden.
    """
    if kind == ReviewTargetKind.RECIPE:
        recipe = recipe_selector.get_recipe_ref(
            slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        if recipe is None:
            raise ReviewTargetNotFoundError
        return recipe.id, recipe.author_id, recipe.title

    course = course_selector.get_course_ref(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if course is None:
        raise ReviewTargetNotFoundError
    return course.id, course.instructor_id, course.title


def create_review(
    *, user_id: int, kind: str, slug: str, data: Mapping[str, Any]
) -> Review:
    """Create an active review of a visible target.

    Args:
        user_id: Primary key of the reviewer.
        kind: A value of :class:`ReviewTargetKind`.
        slug: The target's slug.
        data: Validated payload (``rating``, optional ``comment``).

    Returns:
        The created review, reviewer preloaded.

    Raises:
        ReviewTargetNotFoundError: If the target is absent or hidden.
        OwnContentReviewError: If the reviewer owns the target.
        AlreadyReviewedError: If an active review already exists.
    """
    target_id, owner_id, target_title = resolve_target(
        kind=kind, slug=slug, viewer_id=user_id
    )
    if owner_id == user_id:
        raise OwnContentReviewError

    comment = review_validator.normalize_comment(data.get("comment"))
    review = review_repository.create_review(
        user_id=user_id,
        rating=data["rating"],
        comment=comment,
        recipe_id=target_id if kind == ReviewTargetKind.RECIPE else None,
        course_id=target_id if kind == ReviewTargetKind.COURSE else None,
    )
    logger.info(
        "review_created review_id=%s %s_id=%s by=%s", review.pk, kind, target_id, user_id
    )
    saved = _reload(review_id=review.pk, viewer_id=user_id)
    # Best-effort, post-commit; a notification problem never fails the
    # review (ADR 0016). The self-review case cannot reach here.
    notification_service.notify_review_received(
        owner_id=owner_id,
        reviewer_handle=saved.user.username,
        target_kind=kind,
        target_title=target_title,
        target_slug=slug,
        rating=data["rating"],
    )
    return saved


def update_review(
    *,
    review_id: int,
    viewer_id: int,
    viewer_is_staff: bool = False,
    data: Mapping[str, Any],
) -> Review:
    """Edit a review (owner) and/or change its status (staff).

    Owners may edit the rating and comment of their own non-deleted review;
    a hidden review stays hidden until a moderator restores it. ``status``
    is moderation and staff-only  403, not 404, because the caller already
    proved they can address the review.

    Args:
        review_id: Primary key of the review.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload; absent keys are unchanged.

    Returns:
        The updated review.

    Raises:
        ReviewNotFoundError: If absent, deleted, or not the caller's.
        ModerationNotAllowedError: If a non-staff caller sends ``status``.
    """
    review = _require_addressable(
        review_id=review_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    if "status" in data:
        if not can_moderate(viewer_is_staff=viewer_is_staff):
            raise ModerationNotAllowedError
        review_repository.set_status(review=review, status=data["status"])
        logger.info(
            "review_moderated review_id=%s status=%s by=%s",
            review.pk,
            data["status"],
            viewer_id,
        )

    comment = (
        review_validator.normalize_comment(data["comment"])
        if "comment" in data
        else None
    )
    review_repository.update_review(
        review=review, rating=data.get("rating"), comment=comment
    )
    return _reload(
        review_id=review.pk, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def delete_review(
    *, review_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Soft-delete a review. Idempotent from the client's perspective.

    The row survives as history; the active-only partial unique frees the
    slot, so the author may write a fresh review later.

    Args:
        review_id: Primary key of the review.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        ReviewNotFoundError: If absent, already deleted, or not the caller's.
    """
    review = _require_addressable(
        review_id=review_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if not can_edit_review(
        reviewer_id=review.user_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise ReviewNotFoundError
    review_repository.soft_delete(review=review)
    logger.info("review_deleted review_id=%s by=%s", review_id, viewer_id)


def _require_addressable(
    *, review_id: int, viewer_id: int, viewer_is_staff: bool
) -> Review:
    """Fetch a review the caller may act on; "not yours" is the same 404."""
    review = review_selector.get_addressable_review(
        review_id=review_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if review is None:
        raise ReviewNotFoundError
    return review


def _reload(*, review_id: int, viewer_id: int, viewer_is_staff: bool = False) -> Review:
    """Re-read a review with its relations for serialization."""
    review = review_selector.get_addressable_review(
        review_id=review_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if review is None:  # pragma: no cover - deleted between write and read
        raise ReviewNotFoundError
    return review


def get_rating_context(
    *, kind: str, slug: str, viewer_id: int | None, viewer_is_staff: bool = False
) -> int:
    """Resolve a target for its public rating summary.

    Args:
        kind: A value of :class:`ReviewTargetKind`.
        slug: The target's slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The target's primary key.

    Raises:
        ReviewTargetNotFoundError: If the target is absent or hidden.
    """
    target_id, _owner, _title = resolve_target(
        kind=kind, slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    return target_id
