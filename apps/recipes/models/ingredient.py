"""Recipe ingredient lines."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.recipes.constants import (
    INGREDIENT_GROUP_MAX_LENGTH,
    INGREDIENT_NAME_MAX_LENGTH,
    INGREDIENT_NOTE_MAX_LENGTH,
    Unit,
)


class RecipeIngredient(TimeStampedModel):
    """One ingredient line within a recipe.

    Named ``RecipeIngredient`` rather than ``Ingredient`` on purpose. A
    canonical ingredient catalogue is planned (``docs/Database.md`` promises
    both names), and taking the shorter name for line rows would later force a
    table rename plus a coordinated frontend rename. Reserving it now is free.

    When the catalogue arrives, this table becomes the through table unchanged:
    a nullable ``ingredient`` FK is added and backfilled by grouping on
    ``normalized_name``. No row moves and no endpoint shape changes  quantity
    and unit are properties of the *line*, not of the ingredient, so they
    already live in the right place.

    A canonical catalogue is deliberately **not** built now: free-text
    ``get_or_create`` would immediately produce "แป้งสาลี", "all purpose flour"
    and "AP flour" as three distinct canonical rows, which is worse than free
    text because it looks authoritative.
    """

    recipe = models.ForeignKey(
        "recipes.Recipe", on_delete=models.CASCADE, related_name="ingredients"
    )
    name = models.CharField(
        max_length=INGREDIENT_NAME_MAX_LENGTH, help_text="Exactly as the author typed it."
    )
    normalized_name = models.CharField(
        max_length=INGREDIENT_NAME_MAX_LENGTH,
        db_index=True,
        help_text=(
            "NFC-normalised, casefolded, whitespace-collapsed form. Powers "
            "'recipes containing X' as an indexed lookup and de-duplicates "
            "lines within a recipe."
        ),
    )
    quantity = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Null means an unmeasured amount, such as 'to taste'.",
    )
    unit = models.CharField(
        max_length=20, choices=Unit.choices, default=Unit.GRAM, blank=True
    )
    note = models.CharField(
        max_length=INGREDIENT_NOTE_MAX_LENGTH,
        blank=True,
        help_text="Preparation note, for example 'sifted' or 'room temperature'.",
    )
    group = models.CharField(
        max_length=INGREDIENT_GROUP_MAX_LENGTH,
        blank=True,
        help_text="Section heading, for example 'For the ganache'.",
    )
    is_optional = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(
        default=0, help_text="Server-assigned from the submitted array order."
    )

    class Meta:
        verbose_name = "recipe ingredient"
        verbose_name_plural = "recipe ingredients"
        # No unique constraint on `position`: it would make reordering require
        # deferred constraints or a two-pass update, because a row-by-row save
        # collides with itself immediately.
        ordering = ("group", "position", "id")
        indexes = [
            models.Index(
                fields=["recipe", "position"], name="recipes_ingredient_order_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the ingredient name."""
        return self.name
