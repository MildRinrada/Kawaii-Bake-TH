"""Read serializers for recipes.

Plain ``Serializer`` throughout, never ``ModelSerializer``. Every relation these
render is prefetched by the selector; a ``SerializerMethodField`` that walked an
un-prefetched relation would reintroduce the N+1 the selectors exist to prevent.
``apps/recipes/tests/test_api_list.py`` asserts the query count to catch exactly
that regression.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.recipe_categories.api.serializers import CategoryRefSerializer


class AuthorRefSerializer(serializers.Serializer):
    """The recipe author, as shown on a card or detail page."""

    username = serializers.CharField(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    def get_display_name(self, obj: Any) -> str:
        """Return the author's display name, falling back to the handle."""
        profile = getattr(obj, "profile", None)
        return (profile.display_name if profile else "") or obj.username

    def get_avatar_url(self, obj: Any) -> str | None:
        """Return the author's absolute avatar URL, if any."""
        profile = getattr(obj, "profile", None)
        avatar = getattr(profile, "avatar", None) if profile else None
        if not avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(avatar.url) if request else avatar.url


class ImageUrlMixin(serializers.Serializer):
    """Renders an image field as an absolute URL.

    Absolute because the frontend runs on a different origin and cannot resolve
    a relative media path.
    """

    def _absolute(self, image: Any) -> str | None:
        """Return the absolute URL of ``image``, or ``None``."""
        if not image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.url) if request else image.url


class RecipeListItemSerializer(ImageUrlMixin):
    """One recipe in a listing.

    Deliberately small: ``description``, ingredients, steps and gallery images
    are detail-only, and the list selector defers or omits them.
    """

    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    difficulty = serializers.CharField(read_only=True)
    prep_minutes = serializers.IntegerField(read_only=True)
    cook_minutes = serializers.IntegerField(read_only=True)
    total_minutes = serializers.IntegerField(read_only=True)
    servings = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    visibility = serializers.CharField(read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    author = AuthorRefSerializer(read_only=True)
    categories = CategoryRefSerializer(many=True, read_only=True)

    def get_cover_image_url(self, obj: Any) -> str | None:
        """Return the absolute cover image URL, if any."""
        return self._absolute(obj.cover_image)


class RecipeIngredientSerializer(serializers.Serializer):
    """One ingredient line."""

    name = serializers.CharField(read_only=True)
    quantity = serializers.DecimalField(
        max_digits=7, decimal_places=3, read_only=True, allow_null=True
    )
    unit = serializers.CharField(read_only=True)
    note = serializers.CharField(read_only=True)
    group = serializers.CharField(read_only=True)
    is_optional = serializers.BooleanField(read_only=True)
    position = serializers.IntegerField(read_only=True)


class RecipeStepSerializer(ImageUrlMixin):
    """One preparation step."""

    position = serializers.IntegerField(read_only=True)
    body = serializers.CharField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True, allow_null=True)
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj: Any) -> str | None:
        """Return the absolute step image URL, if any."""
        return self._absolute(obj.image)


class RecipeImageSerializer(ImageUrlMixin):
    """One gallery image."""

    id = serializers.IntegerField(read_only=True)
    caption = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj: Any) -> str | None:
        """Return the absolute image URL."""
        return self._absolute(obj.image)


class NutritionSerializer(serializers.Serializer):
    """Author-supplied nutrition figures.

    ``source`` is always returned so the frontend can show an "estimated, not
    verified" disclaimer. Nothing here is computed by the backend.
    """

    basis = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    serving_size_grams = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    calories_kcal = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    protein_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    carbohydrate_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    sugar_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    fat_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    saturated_fat_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    fiber_g = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    sodium_mg = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )
    cholesterol_mg = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True
    )


class RecipeDetailSerializer(RecipeListItemSerializer):
    """A full recipe."""

    description = serializers.CharField(read_only=True)
    ingredients = RecipeIngredientSerializer(many=True, read_only=True)
    steps = RecipeStepSerializer(many=True, read_only=True)
    images = RecipeImageSerializer(many=True, read_only=True)
    nutrition = serializers.SerializerMethodField()

    def get_nutrition(self, obj: Any) -> dict[str, Any] | None:
        """Return the nutrition payload, or ``None`` when unset.

        Uses the ``nutrition`` attribute loaded by the detail selector's
        ``select_related``; a recipe without a row simply has none.
        """
        nutrition = getattr(obj, "nutrition", None)
        if nutrition is None:
            return None
        return NutritionSerializer(nutrition).data
