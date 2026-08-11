"""Write-side database access for favorites."""

from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.favorites.models import Favorite


def create_or_get(
    *, user_id: int, recipe_id: int | None = None, course_id: int | None = None
) -> tuple[Favorite, bool]:
    """Create a favorite, tolerating a concurrent duplicate.

    The unique constraints are the arbiter; a double-tap resolves to a fetch,
    exactly like enrollment.

    Args:
        user_id: Primary key of the user.
        recipe_id: Target recipe, when favoriting a recipe.
        course_id: Target course, when favoriting a course.

    Returns:
        The favorite and whether it was newly created.
    """
    try:
        with transaction.atomic():
            favorite = Favorite.objects.create(
                user_id=user_id, recipe_id=recipe_id, course_id=course_id
            )
            return favorite, True
    except IntegrityError:
        return (
            Favorite.objects.get(
                user_id=user_id, recipe_id=recipe_id, course_id=course_id
            ),
            False,
        )


def delete(
    *, user_id: int, recipe_id: int | None = None, course_id: int | None = None
) -> int:
    """Remove a favorite. Idempotent  absent rows delete zero.

    Args:
        user_id: Primary key of the user.
        recipe_id: Target recipe, when unfavoriting a recipe.
        course_id: Target course, when unfavoriting a course.

    Returns:
        How many rows were deleted (0 or 1).
    """
    deleted, _ = Favorite.objects.filter(
        user_id=user_id, recipe_id=recipe_id, course_id=course_id
    ).delete()
    return deleted
