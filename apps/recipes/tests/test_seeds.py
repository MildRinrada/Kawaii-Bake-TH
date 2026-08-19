"""Tests for the bundled recipe seed data and the ``seed_recipes`` command.

The data is checked without touching the database wherever possible: a broken
seed should fail the suite, not the person running the command against a fresh
install.
"""

from __future__ import annotations

from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from apps.recipe_categories.models import RecipeCategory
from apps.recipes.constants import RecipeStatus, Unit
from apps.recipes.models import Recipe
from apps.recipes.seeds import SEEDS_BY_CATEGORY, build_payload
from apps.recipes.validators import (
    ingredient_validator,
    recipe_validator,
    step_validator,
)
from apps.users.tests.factories import create_user

SEEDS_PER_CATEGORY = 20


def _all_payloads() -> list[tuple[str, dict]]:
    """Return every seed expanded into a payload, tagged with its category."""
    return [
        (category, build_payload(seed=seed, category_slug=category))
        for category, seeds in SEEDS_BY_CATEGORY.items()
        for seed in seeds
    ]


class SeedDataTests(TestCase):
    """The seed literals themselves  no database involved."""

    def test_every_category_carries_twenty_recipes(self) -> None:
        for category, seeds in SEEDS_BY_CATEGORY.items():
            with self.subTest(category=category):
                self.assertEqual(len(seeds), SEEDS_PER_CATEGORY)

    def test_slugs_are_unique_across_every_category(self) -> None:
        slugs = [payload["slug"] for _category, payload in _all_payloads()]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_every_seed_passes_the_domain_validators(self) -> None:
        # The command runs exactly these before writing; catching a bad seed
        # here means it never reaches someone's terminal as a CommandError.
        for category, payload in _all_payloads():
            with self.subTest(seed=f"{category}/{payload['slug']}"):
                try:
                    recipe_validator.validate_core(payload)
                    ingredient_validator.validate_lines(payload["ingredients"])
                    step_validator.validate_steps(payload["steps"])
                except ValidationError as error:  # pragma: no cover - failure path
                    self.fail(f"{category}/{payload['slug']}: {error.message_dict}")

    def test_every_seed_is_complete_enough_to_publish(self) -> None:
        for category, payload in _all_payloads():
            with self.subTest(seed=f"{category}/{payload['slug']}"):
                self.assertTrue(payload["ingredients"])
                self.assertTrue(payload["steps"])
                self.assertTrue(payload["category_slugs"])

    def test_units_are_valid_choices(self) -> None:
        valid = {choice.value for choice in Unit}
        for category, payload in _all_payloads():
            for line in payload["ingredients"]:
                with self.subTest(seed=f"{category}/{payload['slug']}", line=line["name"]):
                    self.assertIn(line["unit"], valid | {""})

    def test_seeds_are_filed_under_the_category_they_belong_to(self) -> None:
        for category, payload in _all_payloads():
            with self.subTest(seed=f"{category}/{payload['slug']}"):
                self.assertEqual(payload["category_slugs"], [category])


class SeedRecipesCommandTests(TestCase):
    """The command, against a small slice of the data."""

    def setUp(self) -> None:
        self.author = create_user(email="seeder@example.com")
        # The taxonomy is seeded by migration; assert rather than create, so a
        # missing category fails loudly instead of being papered over.
        self.assertTrue(RecipeCategory.objects.filter(slug="bread").exists())

    def _seed(self, **options: object) -> str:
        out = StringIO()
        call_command(
            "seed_recipes",
            author=self.author.email,
            categories="bread",
            limit=3,
            stdout=out,
            **options,
        )
        return out.getvalue()

    def test_creates_published_recipes_with_children(self) -> None:
        self._seed()

        recipes = Recipe.objects.filter(author=self.author)
        self.assertEqual(recipes.count(), 3)

        recipe = recipes.get(slug="bread-hokkaido-milk-loaf")
        self.assertEqual(recipe.status, RecipeStatus.PUBLISHED)
        self.assertIsNotNone(recipe.published_at)
        self.assertEqual(
            recipe.total_minutes, recipe.prep_minutes + recipe.cook_minutes
        )
        self.assertTrue(recipe.ingredients.exists())
        self.assertTrue(recipe.steps.exists())
        self.assertEqual([category.slug for category in recipe.categories.all()], ["bread"])
        self.assertIsNotNone(recipe.nutrition)

    def test_publishes_without_a_cover_image(self) -> None:
        # The deliberate exception to `publish_validator`: artwork is attached
        # separately, and waiting for it would leave the catalogue invisible.
        self._seed()
        recipe = Recipe.objects.get(slug="bread-hokkaido-milk-loaf")
        self.assertFalse(recipe.cover_image)
        self.assertEqual(recipe.status, RecipeStatus.PUBLISHED)

    def test_running_twice_skips_existing_slugs(self) -> None:
        self._seed()
        output = self._seed()

        self.assertEqual(Recipe.objects.count(), 3)
        self.assertIn("0 created, 0 replaced, 3 skipped", output)

    def test_replace_refreshes_an_existing_seed(self) -> None:
        self._seed()
        recipe = Recipe.objects.get(slug="bread-hokkaido-milk-loaf")
        recipe.title = "ชื่อที่ถูกแก้ด้วยมือ"
        recipe.save(update_fields=["title"])

        self._seed(replace=True)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, "โชกุปังนมฮอกไกโด")
        self.assertEqual(Recipe.objects.count(), 3)

    def test_dry_run_writes_nothing(self) -> None:
        output = self._seed(dry_run=True)

        self.assertEqual(Recipe.objects.count(), 0)
        self.assertIn("[dry run]", output)

    def test_draft_status_leaves_published_at_unset(self) -> None:
        self._seed(status=RecipeStatus.DRAFT)

        recipe = Recipe.objects.get(slug="bread-hokkaido-milk-loaf")
        self.assertEqual(recipe.status, RecipeStatus.DRAFT)
        self.assertIsNone(recipe.published_at)

    def test_published_timestamps_are_spread_apart(self) -> None:
        self._seed()

        stamps = list(
            Recipe.objects.order_by("-published_at").values_list("published_at", flat=True)
        )
        self.assertEqual(len(set(stamps)), 3)
