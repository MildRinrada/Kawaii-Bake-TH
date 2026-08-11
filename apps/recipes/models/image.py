"""Recipe gallery images."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.recipes.constants import IMAGE_CAPTION_MAX_LENGTH, RECIPE_IMAGE_UPLOAD_DIR
from apps.recipes.utils import build_upload_path
from infrastructure.storage import get_media_storage


def recipe_image_upload_to(instance: RecipeImage, filename: str) -> str:
    """Build the storage path for a gallery image."""
    return build_upload_path(directory=RECIPE_IMAGE_UPLOAD_DIR, filename=filename)


class RecipeImage(TimeStampedModel):
    """An additional photo attached to a recipe.

    The **cover** image is not stored here  it is a column on ``Recipe``. The
    cover is read on every list row and every card in the product, so keeping it
    on the row costs zero joins, and "exactly one cover" becomes a schema
    invariant rather than a constraint that has to be trusted and repaired.
    This table holds only the supplementary gallery.
    """

    recipe = models.ForeignKey(
        "recipes.Recipe", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        upload_to=recipe_image_upload_to, storage=get_media_storage
    )
    caption = models.CharField(max_length=IMAGE_CAPTION_MAX_LENGTH, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "recipe image"
        verbose_name_plural = "recipe images"
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=["recipe", "position"], name="recipes_image_order_idx"),
        ]

    def __str__(self) -> str:
        """Return a readable label."""
        return f"Image {self.pk} for recipe {self.recipe_id}"
