"""Tests for recipe models and the pure helpers around them."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.recipes.constants import RecipeStatus
from apps.recipes.models import Nutrition, Recipe
from apps.recipes.tests.factories import (
    THAI_INGREDIENT,
    THAI_TITLE,
    create_published_recipe,
    create_recipe,
)
from apps.recipes.utils import (
    build_slug_base,
    normalize_ingredient_name,
    slug_with_suffix,
)
from apps.users.tests.factories import create_user


class SlugHelperTests(TestCase):
    """Slug generation, including the Thai cases that fail silently."""

    def test_ascii_title_produces_readable_slug(self) -> None:
        self.assertEqual(build_slug_base("Chocolate Croissant"), "chocolate-croissant")

    def test_thai_title_survives_slugification(self) -> None:
        # This is the trap `allow_unicode=True` exists to avoid: without it,
        # `slugify` returns "" for Thai and every Thai-titled recipe would
        # silently fall back to a random slug.
        from django.utils.text import slugify

        self.assertEqual(slugify(THAI_TITLE), "")

        base = build_slug_base(THAI_TITLE)
        self.assertNotEqual(base, "")
        # Thai script is preserved. It is lossy — `slugify` drops combining
        # tone marks and vowel signs — which is acceptable for a URL identifier
        # (English slugs lose accents the same way) and is why collisions get a
        # random suffix.
        self.assertTrue(any("฀" <= char <= "๿" for char in base))
        self.assertLess(len(base), len(THAI_TITLE))

    def test_unusable_titles_produce_empty_base(self) -> None:
        for title in ("!!!", "   ", "12345", "search"):
            with self.subTest(title=title):
                self.assertEqual(build_slug_base(title), "")

    def test_reserved_word_is_rejected_as_a_base(self) -> None:
        self.assertEqual(build_slug_base("publish"), "")

    def test_suffix_is_added_to_a_base(self) -> None:
        result = slug_with_suffix("brownie")

        self.assertTrue(result.startswith("brownie-"))
        self.assertNotEqual(result, slug_with_suffix("brownie"))

    def test_suffix_without_base_still_yields_a_slug(self) -> None:
        self.assertTrue(slug_with_suffix("").startswith("recipe-"))


class IngredientNormalisationTests(TestCase):
    """NFC normalisation, which Thai text depends on."""

    def test_case_and_whitespace_are_collapsed(self) -> None:
        self.assertEqual(
            normalize_ingredient_name("  All   Purpose  FLOUR "), "all purpose flour"
        )

    def test_thai_text_is_preserved(self) -> None:
        self.assertEqual(
            normalize_ingredient_name(THAI_INGREDIENT), THAI_INGREDIENT.casefold()
        )

    def test_decomposed_and_composed_forms_compare_equal(self) -> None:
        import unicodedata

        composed = "café"
        decomposed = unicodedata.normalize("NFD", composed)

        self.assertNotEqual(composed, decomposed)
        self.assertEqual(
            normalize_ingredient_name(composed), normalize_ingredient_name(decomposed)
        )


class RecipeModelTests(TestCase):
    """Model-level invariants."""

    def setUp(self) -> None:
        self.user = create_user()

    def test_slug_uniqueness_is_case_insensitive(self) -> None:
        create_recipe(author=self.user, slug="brownie")

        with self.assertRaises(IntegrityError), transaction.atomic():
            create_recipe(author=self.user, slug="Brownie")

    def test_defaults_are_draft_and_public(self) -> None:
        recipe = create_recipe(author=self.user)

        self.assertEqual(recipe.status, RecipeStatus.DRAFT)
        self.assertFalse(recipe.is_published)
        self.assertIsNone(recipe.published_at)

    def test_slug_is_not_frozen_before_first_publication(self) -> None:
        recipe = create_recipe(author=self.user)

        self.assertFalse(recipe.slug_is_frozen)

    def test_slug_freezes_once_published_at_is_set(self) -> None:
        recipe = create_published_recipe(author=self.user)

        self.assertTrue(recipe.slug_is_frozen)

    def test_author_reverse_accessor_is_recipes(self) -> None:
        # Reserved in docs/Database.md; other apps will rely on this name.
        recipe = create_recipe(author=self.user)

        self.assertIn(recipe, self.user.recipes.all())

    def test_deleting_a_recipe_cascades_to_children(self) -> None:
        recipe = create_recipe(
            author=self.user, with_ingredients=True, with_steps=True
        )
        Nutrition.objects.create(recipe=recipe, calories_kcal=250)
        recipe_id = recipe.pk

        recipe.delete()

        self.assertFalse(Recipe.objects.filter(pk=recipe_id).exists())
        self.assertFalse(Nutrition.objects.filter(pk=recipe_id).exists())

    def test_nutrition_uses_the_recipe_as_primary_key(self) -> None:
        recipe = create_recipe(author=self.user)

        nutrition = Nutrition.objects.create(recipe=recipe)

        self.assertEqual(nutrition.pk, recipe.pk)

    def test_missing_nutrition_is_absent_not_an_error(self) -> None:
        recipe = create_recipe(author=self.user)

        self.assertIsNone(getattr(recipe, "nutrition", None))

    def test_total_minutes_is_stored_for_indexed_sorting(self) -> None:
        recipe = create_recipe(author=self.user, prep_minutes=15, cook_minutes=45)

        self.assertEqual(recipe.total_minutes, 60)

    def test_published_at_survives_unpublishing(self) -> None:
        published = timezone.now()
        recipe = create_published_recipe(author=self.user, published_at=published)

        recipe.status = RecipeStatus.DRAFT
        recipe.save(update_fields=["status"])
        recipe.refresh_from_db()

        self.assertEqual(recipe.published_at, published)
        self.assertTrue(recipe.slug_is_frozen)
