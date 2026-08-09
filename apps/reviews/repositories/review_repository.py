"""Write-side database access for reviews.

**This module is the single choke point for review mutations**, and therefore
the only caller of ``course_service.sync_rating_aggregate`` (ADR 0021): every
create/edit/moderate/soft-delete of a course-targeted review pushes the fresh
aggregate inside the same transaction. A mutation path that bypasses this
module is a bug by definition; ``manage.py rebuild_rating_aggregates``
reconciles if one ever ships.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count

from apps.courses.services import course_service
from apps.reviews.constants import ReviewStatus
from apps.reviews.exceptions import AlreadyReviewedError
from apps.reviews.models import Review


def sync_course_rating(*, course_id: int) -> None:
    """Recompute a course's active-review aggregate and push it to courses.

    Args:
        course_id: Primary key of the reviewed course.
    """
    aggregates = Review.objects.filter(
        course_id=course_id, status=ReviewStatus.ACTIVE
    ).aggregate(average=Avg("rating"), total=Count("id"))
    average = aggregates["average"]
    course_service.sync_rating_aggregate(
        course_id=course_id,
        average=(
            Decimal(average).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if average is not None
            else None
        ),
        count=aggregates["total"],
    )


def create_review(
    *,
    user_id: int,
    rating: int,
    comment: str,
    recipe_id: int | None = None,
    course_id: int | None = None,
) -> Review:
    """Create an active review, letting the constraint arbitrate duplicates.

    Attempt-and-catch in a savepoint: a concurrent double-submit surfaces as
    ``IntegrityError`` from the partial unique and resolves to the domain
    error, exactly like enrollment.

    Args:
        user_id: Primary key of the reviewer.
        rating: 1–5.
        comment: Optional text, already stripped.
        recipe_id: Target recipe, when reviewing a recipe.
        course_id: Target course, when reviewing a course.

    Returns:
        The created review.

    Raises:
        AlreadyReviewedError: If the user already has an active review here.
    """
    try:
        with transaction.atomic():
            review = Review.objects.create(
                user_id=user_id,
                rating=rating,
                comment=comment,
                recipe_id=recipe_id,
                course_id=course_id,
            )
            if course_id is not None:
                sync_course_rating(course_id=course_id)
            return review
    except IntegrityError as error:
        raise AlreadyReviewedError from error


def update_review(*, review: Review, rating: int | None, comment: str | None) -> Review:
    """Apply an owner edit in a single UPDATE.

    Args:
        review: The review to update.
        rating: New rating, or ``None`` to keep.
        comment: New comment, or ``None`` to keep.

    Returns:
        The updated review.
    """
    changes: list[str] = ["updated_at"]
    if rating is not None:
        review.rating = rating
        changes.append("rating")
    if comment is not None:
        review.comment = comment
        changes.append("comment")
    if len(changes) > 1:
        with transaction.atomic():
            review.save(update_fields=changes)
            if "rating" in changes and review.course_id is not None:
                sync_course_rating(course_id=review.course_id)
    return review


def set_status(*, review: Review, status: str) -> Review:
    """Change a review's moderation status.

    Args:
        review: The review to update.
        status: A value of :class:`ReviewStatus`.

    Returns:
        The updated review.
    """
    if review.status != status:
        with transaction.atomic():
            review.status = status
            review.save(update_fields=["status", "updated_at"])
            if review.course_id is not None:
                sync_course_rating(course_id=review.course_id)
    return review


def soft_delete(*, review: Review) -> Review:
    """Mark a review deleted. The row survives — history is never erased."""
    return set_status(review=review, status=ReviewStatus.DELETED)
