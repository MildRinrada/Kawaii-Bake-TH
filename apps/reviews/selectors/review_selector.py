"""Read-side queries for reviews."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q, QuerySet

from apps.reviews.constants import ReviewStatus
from apps.reviews.models import Review


@dataclass(frozen=True)
class UserReviewFact:
    """One review as a taste signal: what was rated, and how.

    Part of the public cross-app API (Phase 12). Exactly one of
    ``recipe_id``/``course_id`` is set  the model's own constraint.
    """

    recipe_id: int | None
    course_id: int | None
    rating: int


def review_facts_for_user(*, user_id: int) -> list[UserReviewFact]:
    """The user's active reviews as plain facts, in one query.

    Active only  a deleted or moderated-away review stops shaping
    recommendations, the same rule the XP ledger follows (Phase 9).

    Args:
        user_id: Primary key of the user.

    Returns:
        The facts, oldest first for determinism.
    """
    return [
        UserReviewFact(**row)
        for row in Review.objects.filter(user_id=user_id, status=ReviewStatus.ACTIVE)
        .order_by("id")
        .values("recipe_id", "course_id", "rating")
    ]


def list_for_recipe(*, recipe_id: int) -> QuerySet[Review]:
    """Active reviews of one recipe, newest first, reviewer preloaded.

    Args:
        recipe_id: Primary key of the recipe.

    Returns:
        A lazy queryset for pagination.
    """
    return (
        Review.objects.filter(recipe_id=recipe_id, status=ReviewStatus.ACTIVE)
        .select_related("user", "user__profile", "recipe")
        .order_by("-created_at", "-id")
    )


def list_for_course(*, course_id: int) -> QuerySet[Review]:
    """Active reviews of one course, newest first, reviewer preloaded.

    Args:
        course_id: Primary key of the course.

    Returns:
        A lazy queryset for pagination.
    """
    return (
        Review.objects.filter(course_id=course_id, status=ReviewStatus.ACTIVE)
        .select_related("user", "user__profile", "course")
        .order_by("-created_at", "-id")
    )


def list_all(
    *,
    rating: int | None = None,
    review_status: str = "",
    target: str = "",
    search: str = "",
    username: str = "",
) -> QuerySet[Review]:
    """Every review across recipes and courses, for the staff surface.

    Soft-deleted rows are excluded unless explicitly asked for by
    ``review_status``: they are tombstones, not content.

    Args:
        rating: Restrict to one star value.
        review_status: Restrict to one :class:`ReviewStatus`; empty means
            active and hidden.
        target: ``recipe`` or ``course``; empty means both.
        search: Matches the comment or the reviewer's username.

    Returns:
        A lazy queryset for pagination, newest first.
    """
    queryset = Review.objects.select_related(
        "user", "user__profile", "recipe", "course"
    )

    if review_status:
        queryset = queryset.filter(status=review_status)
    else:
        queryset = queryset.exclude(status=ReviewStatus.DELETED)

    if rating is not None:
        queryset = queryset.filter(rating=rating)
    if target == "recipe":
        queryset = queryset.filter(recipe__isnull=False)
    elif target == "course":
        queryset = queryset.filter(course__isnull=False)

    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(comment__icontains=cleaned)
            | Q(user__username__icontains=cleaned)
        )
    if username.strip():
        # Exact handle - the per-user activity panel needs a count that
        # cannot be inflated by a comment mentioning the handle.
        queryset = queryset.filter(user__username__iexact=username.strip())

    return queryset.order_by("-created_at", "-id")


def active_review_count(*, user_id: int) -> int:
    """How many active reviews the user has written.

    Part of the public cross-app API (Phase 9)  the fact count behind
    review XP. Active only: a deleted or moderated-away review stops
    counting toward new derivations.

    Args:
        user_id: Primary key of the user.

    Returns:
        The active review count.
    """
    return Review.objects.filter(
        user_id=user_id, status=ReviewStatus.ACTIVE
    ).count()


def get_addressable_review(
    *, review_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> Review | None:
    """Fetch one review the viewer may act on.

    Owners address their own non-deleted reviews; staff address any
    non-deleted review. Deleted rows are 404 for everyone  they exist only
    as history.

    Args:
        review_id: Primary key of the review.
        viewer_id: Primary key of the viewer.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The review, or ``None``  absent, deleted and someone-else's are
        indistinguishable to the client.
    """
    queryset = Review.objects.exclude(status=ReviewStatus.DELETED).select_related(
        "user", "user__profile", "recipe", "course"
    )
    if not viewer_is_staff:
        queryset = queryset.filter(user_id=viewer_id)
    return queryset.filter(pk=review_id).first()
