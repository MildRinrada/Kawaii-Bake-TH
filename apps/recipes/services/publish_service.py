"""Recipe lifecycle transitions.

This module owns the state machine and nothing else. It never touches
ingredients, steps or images.

    DRAFT ──publish (validated)──▶ PUBLISHED ──archive──▶ ARCHIVED
      ▲ └──────── archive ──────────────┘                    │
      └──────────────── unpublish / restore ─────────────────┘

Every transition is reversible; only ``DELETE`` is terminal.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.recipes.constants import RecipeStatus, RecipeVisibility
from apps.recipes.exceptions import RecipeNotVisibleError
from apps.recipes.models import Recipe
from apps.recipes.permissions.recipe_permissions import can_change_status
from apps.recipes.repositories import recipe_repository
from apps.recipes.selectors import recipe_selector
from apps.recipes.validators.publish_validator import assert_publishable

logger = logging.getLogger("kawaiibake.recipes")


def _require_transitionable(
    *, slug: str, viewer_id: int, viewer_is_staff: bool
) -> Recipe:
    """Fetch a recipe whose status the caller may change."""
    recipe = recipe_selector.get_editable_recipe(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe is None or not can_change_status(
        author_id=recipe.author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise RecipeNotVisibleError
    return recipe


def publish(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Recipe:
    """Publish a recipe after checking it is complete.

    Idempotent: publishing an already-published recipe is a no-op rather than an
    error. ``published_at`` is stamped only the first time, which is what keeps
    the slug frozen across an unpublish/republish cycle.

    An archived recipe is re-validated on its way back to published  rules may
    have changed since it was archived.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The published recipe.

    Raises:
        RecipeNotVisibleError: If absent or not the caller's to change.
        RecipeNotPublishableError: If the recipe is incomplete.
    """
    recipe = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe.status == RecipeStatus.PUBLISHED:
        return recipe

    assert_publishable(recipe)

    changes: dict[str, object] = {"status": RecipeStatus.PUBLISHED}
    if recipe.published_at is None:
        changes["published_at"] = timezone.now()

    recipe_repository.update_recipe(recipe=recipe, changes=changes)
    logger.info("recipe_published recipe_id=%s by=%s", recipe.pk, viewer_id)
    return recipe


def unpublish(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Recipe:
    """Return a published recipe to draft.

    ``published_at`` is deliberately retained, so the original publication date
    survives and the slug stays frozen  a URL that has already been shared must
    not become reusable.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The recipe, now a draft.

    Raises:
        RecipeNotVisibleError: If absent or not the caller's to change.
    """
    recipe = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe.status != RecipeStatus.DRAFT:
        recipe_repository.update_recipe(
            recipe=recipe, changes={"status": RecipeStatus.DRAFT}
        )
        logger.info("recipe_unpublished recipe_id=%s by=%s", recipe.pk, viewer_id)
    return recipe


def archive(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Recipe:
    """Archive a recipe.

    Archiving is the reversible "remove it from view" action, as opposed to
    ``DELETE``, which is permanent. No completeness check applies.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The archived recipe.

    Raises:
        RecipeNotVisibleError: If absent or not the caller's to change.
    """
    recipe = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe.status != RecipeStatus.ARCHIVED:
        recipe_repository.update_recipe(
            recipe=recipe, changes={"status": RecipeStatus.ARCHIVED}
        )
        logger.info("recipe_archived recipe_id=%s by=%s", recipe.pk, viewer_id)
    return recipe


def set_visibility(
    *, slug: str, visibility: str, viewer_id: int, viewer_is_staff: bool = False
) -> Recipe:
    """Change who may see a recipe.

    Independent of ``status``: a recipe can be published and private, or a
    public draft that nobody can reach yet.

    Args:
        slug: The recipe slug.
        visibility: A value of :class:`RecipeVisibility`.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The updated recipe.

    Raises:
        RecipeNotVisibleError: If absent or not the caller's to change.
        ValueError: If ``visibility`` is not a valid choice.
    """
    if visibility not in RecipeVisibility.values:
        raise ValueError(f"Unknown visibility: {visibility!r}")

    recipe = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    recipe_repository.update_recipe(recipe=recipe, changes={"visibility": visibility})
    return recipe
