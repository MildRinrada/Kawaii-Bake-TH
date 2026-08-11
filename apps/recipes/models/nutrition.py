"""Estimated nutrition  structure only."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.recipes.constants import NutritionBasis, NutritionSource


class Nutrition(TimeStampedModel):
    """Nutrition figures for a recipe.

    **Structure only in Phase 2.** The table exists and the API round-trips it,
    but nothing in the codebase performs any arithmetic: no summing over
    ingredients, no unit conversion, no per-serving division. Every value is
    author-supplied and echoed back verbatim.

    Uses the recipe as its primary key, the same pattern as ``users.Profile``:
    the one-to-one is enforced by the database, there is no surrogate key or
    extra index, and ``get_or_create(pk=recipe_id)`` is race-safe. No row is
    created automatically, so recipes without nutrition cost nothing.

    Every figure is nullable, and null means *unknown* rather than zero  a
    distinction a JSON blob could express but could not enforce.

    ``basis`` and ``source`` ship now, before anything can produce an estimate,
    for the same reason ``IssuedCredential.status`` shipped before two-factor
    auth existed: adding the estimator later becomes additive instead of a
    breaking change. Without ``basis`` every stored number would be ambiguous
    and no later migration could repair it.
    """

    recipe = models.OneToOneField(
        "recipes.Recipe",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="nutrition",
    )

    basis = models.CharField(
        max_length=20,
        choices=NutritionBasis.choices,
        default=NutritionBasis.PER_SERVING,
    )
    source = models.CharField(
        max_length=20,
        choices=NutritionSource.choices,
        default=NutritionSource.MANUAL,
        help_text="Phase 2 only ever writes 'manual'.",
    )
    calculated_at = models.DateTimeField(
        null=True, blank=True, help_text="Set by the future estimator; unused in Phase 2."
    )

    serving_size_grams = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    calories_kcal = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    protein_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    carbohydrate_g = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    sugar_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    saturated_fat_g = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    fiber_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sodium_mg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    cholesterol_mg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "nutrition"
        verbose_name_plural = "nutrition"

    def __str__(self) -> str:
        """Return a readable label."""
        return f"Nutrition<{self.recipe_id}>"
