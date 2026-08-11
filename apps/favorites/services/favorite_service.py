"""Business logic for favorites: toggle on, toggle off."""

from __future__ import annotations

import logging

from apps.courses.selectors import course_selector
from apps.favorites.constants import FavoriteTargetKind
from apps.favorites.exceptions import FavoriteTargetNotFoundError
from apps.favorites.models import Favorite
from apps.favorites.repositories import favorite_repository
from apps.recipes.selectors import recipe_selector

logger = logging.getLogger("kawaiibake.favorites")


def _resolve_target(*, kind: str, slug: str, user_id: int) -> int:
    """Resolve a target slug to its id through the detail visibility rule.

    Private content cannot be favorited  hidden and absent are the same 404.

    Raises:
        FavoriteTargetNotFoundError: If the target is absent or hidden.
    """
    if kind == FavoriteTargetKind.RECIPE:
        recipe = recipe_selector.get_recipe_ref(slug=slug, viewer_id=user_id)
        if recipe is None:
            raise FavoriteTargetNotFoundError
        return recipe.id

    course = course_selector.get_course_ref(slug=slug, viewer_id=user_id)
    if course is None:
        raise FavoriteTargetNotFoundError
    return course.id


def favorite(*, user_id: int, kind: str, slug: str) -> tuple[Favorite, bool]:
    """Favorite a visible target. Idempotent  a toggle, like enroll.

    Args:
        user_id: Primary key of the user.
        kind: A value of :class:`FavoriteTargetKind`.
        slug: The target's slug.

    Returns:
        The favorite and whether it was newly created.

    Raises:
        FavoriteTargetNotFoundError: If the target is absent or hidden.
    """
    target_id = _resolve_target(kind=kind, slug=slug, user_id=user_id)
    row, created = favorite_repository.create_or_get(
        user_id=user_id,
        recipe_id=target_id if kind == FavoriteTargetKind.RECIPE else None,
        course_id=target_id if kind == FavoriteTargetKind.COURSE else None,
    )
    if created:
        logger.info("favorited %s_id=%s by=%s", kind, target_id, user_id)
    return row, created


def unfavorite(*, user_id: int, kind: str, slug: str) -> None:
    """Remove a favorite. Idempotent  removing what is absent is a no-op.

    Args:
        user_id: Primary key of the user.
        kind: A value of :class:`FavoriteTargetKind`.
        slug: The target's slug.

    Raises:
        FavoriteTargetNotFoundError: If the target is absent or hidden 
            fail-closed: a hidden target cannot be addressed even to
            unfavorite it (the row silently leaves the list instead).
    """
    target_id = _resolve_target(kind=kind, slug=slug, user_id=user_id)
    deleted = favorite_repository.delete(
        user_id=user_id,
        recipe_id=target_id if kind == FavoriteTargetKind.RECIPE else None,
        course_id=target_id if kind == FavoriteTargetKind.COURSE else None,
    )
    if deleted:
        logger.info("unfavorited %s_id=%s by=%s", kind, target_id, user_id)
