"""Business logic for recipe gallery images."""

from __future__ import annotations

from typing import Any

from apps.recipes.exceptions import RecipeNotVisibleError
from apps.recipes.models import RecipeImage
from apps.recipes.permissions.recipe_permissions import can_edit_recipe
from apps.recipes.repositories import image_repository
from apps.recipes.selectors import recipe_selector
from apps.recipes.validators.image_validator import (
    validate_gallery_capacity,
    validate_recipe_image,
)


def add_gallery_image(
    *,
    slug: str,
    viewer_id: int,
    viewer_is_staff: bool = False,
    image: Any,
    caption: str = "",
) -> RecipeImage:
    """Attach an image to a recipe's gallery.

    Args:
        slug: The recipe slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        image: The uploaded file.
        caption: Optional caption.

    Returns:
        The created image.

    Raises:
        RecipeNotVisibleError: If absent or not the caller's to edit.
        django.core.exceptions.ValidationError: If the file is unacceptable or
            the gallery is full.
    """
    recipe = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    validate_recipe_image(image)
    validate_gallery_capacity(current_count=image_repository.count_images(recipe=recipe))

    return image_repository.add_image(recipe=recipe, image=image, caption=caption)


def remove_gallery_image(
    *, slug: str, image_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Delete one gallery image.

    Args:
        slug: The recipe slug.
        image_id: Primary key of the image.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        RecipeNotVisibleError: If the recipe or image is absent, or the caller
            may not edit the recipe.
    """
    recipe = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    # Scoped to the recipe, so an id belonging to another recipe cannot be
    # deleted by guessing it.
    image = image_repository.get_image(recipe=recipe, image_id=image_id)
    if image is None:
        raise RecipeNotVisibleError("Image not found.")

    image_repository.delete_image(image=image)


def _require_editable(*, slug: str, viewer_id: int, viewer_is_staff: bool):
    """Fetch a recipe the caller may edit, or raise the 404 domain error."""
    recipe = recipe_selector.get_editable_recipe(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if recipe is None or not can_edit_recipe(
        author_id=recipe.author_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise RecipeNotVisibleError
    return recipe
