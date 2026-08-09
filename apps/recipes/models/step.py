"""Recipe preparation steps."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.recipes.constants import RECIPE_STEP_UPLOAD_DIR, STEP_BODY_MAX_LENGTH
from apps.recipes.utils import build_upload_path
from infrastructure.storage import get_media_storage


def step_image_upload_to(instance: RecipeStep, filename: str) -> str:
    """Build the storage path for a step illustration."""
    return build_upload_path(directory=RECIPE_STEP_UPLOAD_DIR, filename=filename)


class RecipeStep(TimeStampedModel):
    """One instruction in a recipe's method.

    ``position`` is assigned by the service from the submitted array order —
    never accepted from the client, which routinely sends duplicate or gapped
    values. The array order is unambiguous and JSON preserves it.
    """

    recipe = models.ForeignKey(
        "recipes.Recipe", on_delete=models.CASCADE, related_name="steps"
    )
    position = models.PositiveSmallIntegerField(default=1)
    body = models.TextField(max_length=STEP_BODY_MAX_LENGTH)
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True, help_text="Optional per-step timer."
    )
    image = models.ImageField(
        upload_to=step_image_upload_to, storage=get_media_storage, blank=True
    )

    class Meta:
        verbose_name = "recipe step"
        verbose_name_plural = "recipe steps"
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=["recipe", "position"], name="recipes_step_order_idx"),
        ]

    def __str__(self) -> str:
        """Return a readable label."""
        return f"Step {self.position}"
