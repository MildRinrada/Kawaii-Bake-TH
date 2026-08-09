"""Write serializers for recipes.

Nested serializers are used here for **validation**, which is permitted: they
produce plain dicts in ``validated_data``. What is banned is nested
*persistence* — no ``.save()``, ``.create()`` or ``.update()`` anywhere. The
service layer performs every write.

Read and write shapes are separate classes on purpose. A single serializer used
for both is how ``is_staff`` ends up in a PATCH body.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.recipes.constants import (
    IMAGE_CAPTION_MAX_LENGTH,
    INGREDIENT_GROUP_MAX_LENGTH,
    INGREDIENT_NAME_MAX_LENGTH,
    INGREDIENT_NOTE_MAX_LENGTH,
    MAX_CATEGORIES_PER_RECIPE,
    MAX_INGREDIENTS_PER_RECIPE,
    MAX_SERVINGS,
    MAX_STEPS_PER_RECIPE,
    MIN_SERVINGS,
    STEP_BODY_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
    Difficulty,
    NutritionBasis,
    RecipeVisibility,
    Unit,
)


class IngredientWriteSerializer(StrictSerializer):
    """One submitted ingredient line.

    ``position`` is absent on purpose: the array order *is* the order. Clients
    routinely send duplicate or gapped positions, so the server assigns them.
    """

    name = serializers.CharField(max_length=INGREDIENT_NAME_MAX_LENGTH)
    quantity = serializers.DecimalField(
        max_digits=7, decimal_places=3, required=False, allow_null=True
    )
    unit = serializers.ChoiceField(
        choices=Unit.choices, required=False, allow_blank=True
    )
    note = serializers.CharField(
        max_length=INGREDIENT_NOTE_MAX_LENGTH, required=False, allow_blank=True
    )
    group = serializers.CharField(
        max_length=INGREDIENT_GROUP_MAX_LENGTH, required=False, allow_blank=True
    )
    is_optional = serializers.BooleanField(required=False, default=False)


class StepWriteSerializer(StrictSerializer):
    """One submitted preparation step."""

    body = serializers.CharField(max_length=STEP_BODY_MAX_LENGTH)
    duration_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )


class NutritionWriteSerializer(StrictSerializer):
    """Submitted nutrition figures.

    ``source`` is absent: Phase 2 computes nothing, so everything stored here is
    ``manual`` and the server sets it.
    """

    basis = serializers.ChoiceField(choices=NutritionBasis.choices, required=False)
    serving_size_grams = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    calories_kcal = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    protein_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    carbohydrate_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    sugar_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    fat_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    saturated_fat_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    fiber_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    sodium_mg = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    cholesterol_mg = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )


class RecipeCreateSerializer(StrictSerializer):
    """Validates a recipe creation payload.

    ``status`` is deliberately absent: every recipe starts as a draft and is
    published through the dedicated transition endpoint, which runs the
    completeness checks. Accepting it here would route a publish around them.
    """

    title = serializers.CharField(
        min_length=TITLE_MIN_LENGTH, max_length=TITLE_MAX_LENGTH
    )
    summary = serializers.CharField(
        max_length=SUMMARY_MAX_LENGTH, required=False, allow_blank=True
    )
    description = serializers.CharField(required=False, allow_blank=True)
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, required=False)
    visibility = serializers.ChoiceField(
        choices=RecipeVisibility.choices, required=False
    )
    prep_minutes = serializers.IntegerField(required=False, min_value=0, default=0)
    cook_minutes = serializers.IntegerField(required=False, min_value=0, default=0)
    servings = serializers.IntegerField(
        required=False, min_value=MIN_SERVINGS, max_value=MAX_SERVINGS, default=1
    )
    cover_image = serializers.ImageField(required=False, allow_null=True)

    category_slugs = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        max_length=MAX_CATEGORIES_PER_RECIPE,
    )
    ingredients = IngredientWriteSerializer(
        many=True, required=False, max_length=MAX_INGREDIENTS_PER_RECIPE
    )
    steps = StepWriteSerializer(
        many=True, required=False, max_length=MAX_STEPS_PER_RECIPE
    )
    nutrition = NutritionWriteSerializer(required=False, allow_null=True)


class RecipeUpdateSerializer(StrictSerializer):
    """Validates a partial recipe update.

    Every field is optional; absent means "leave unchanged". Supplying
    ``ingredients`` or ``steps`` **replaces** that whole collection, which is
    also how reordering is expressed.

    ``visibility`` is editable here because it is a plain field with no
    precondition. ``status`` is not: publishing must run the completeness
    checks, so it has its own endpoint.
    """

    title = serializers.CharField(
        min_length=TITLE_MIN_LENGTH, max_length=TITLE_MAX_LENGTH, required=False
    )
    slug = serializers.SlugField(allow_unicode=True, required=False)
    summary = serializers.CharField(
        max_length=SUMMARY_MAX_LENGTH, required=False, allow_blank=True
    )
    description = serializers.CharField(required=False, allow_blank=True)
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, required=False)
    visibility = serializers.ChoiceField(
        choices=RecipeVisibility.choices, required=False
    )
    prep_minutes = serializers.IntegerField(required=False, min_value=0)
    cook_minutes = serializers.IntegerField(required=False, min_value=0)
    servings = serializers.IntegerField(
        required=False, min_value=MIN_SERVINGS, max_value=MAX_SERVINGS
    )
    cover_image = serializers.ImageField(required=False, allow_null=True)

    category_slugs = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        max_length=MAX_CATEGORIES_PER_RECIPE,
    )
    ingredients = IngredientWriteSerializer(
        many=True, required=False, max_length=MAX_INGREDIENTS_PER_RECIPE
    )
    steps = StepWriteSerializer(
        many=True, required=False, max_length=MAX_STEPS_PER_RECIPE
    )
    nutrition = NutritionWriteSerializer(required=False, allow_null=True)


class RecipeImageUploadSerializer(StrictSerializer):
    """Validates a gallery image upload."""

    image = serializers.ImageField()
    caption = serializers.CharField(
        max_length=IMAGE_CAPTION_MAX_LENGTH, required=False, allow_blank=True
    )
