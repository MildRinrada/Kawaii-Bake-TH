"""Write-side database access for recipe gallery images."""

from __future__ import annotations

from typing import Any

from django.db.models import Max

from apps.recipes.models import Recipe, RecipeImage


def add_image(*, recipe: Recipe, image: Any, caption: str = "") -> RecipeImage:
    """Append an image to a recipe's gallery.

    Args:
        recipe: The owning recipe.
        image: The uploaded file.
        caption: Optional caption.

    Returns:
        The created image.
    """
    highest = (
        RecipeImage.objects.filter(recipe=recipe).aggregate(Max("position"))[
            "position__max"
        ]
        or 0
    )
    return RecipeImage.objects.create(
        recipe=recipe, image=image, caption=caption.strip(), position=highest + 1
    )


def get_image(*, recipe: Recipe, image_id: int) -> RecipeImage | None:
    """Fetch one gallery image belonging to a recipe.

    Scoped to the recipe so an id from another recipe cannot be addressed.

    Args:
        recipe: The owning recipe.
        image_id: Primary key of the image.

    Returns:
        The image, or ``None``.
    """
    return RecipeImage.objects.filter(recipe=recipe, pk=image_id).first()


def delete_image(*, image: RecipeImage) -> None:
    """Delete a gallery image row and its stored file.

    Django never deletes files when a row is deleted, so this is explicit.

    Args:
        image: The image to delete.
    """
    stored = image.image
    image.delete()
    if stored:
        stored.delete(save=False)


def count_images(*, recipe: Recipe) -> int:
    """Count a recipe's gallery images.

    Args:
        recipe: The owning recipe.

    Returns:
        The number of images.
    """
    return RecipeImage.objects.filter(recipe=recipe).count()
