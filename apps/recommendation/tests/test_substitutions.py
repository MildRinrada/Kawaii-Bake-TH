"""Ingredient substitution: normalisation, honesty, visibility."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.recipes.constants import RecipeStatus, RecipeVisibility
from apps.recipes.tests.factories import (
    add_ingredient,
    create_published_recipe,
    create_recipe,
)
from apps.recommendation.exceptions import RecipeNotFoundError
from apps.recommendation.services import substitution_service
from apps.users.tests.factories import create_user


def url(slug: str) -> str:
    return f"/api/v1/recipes/{slug}/substitutions/"


class SubstitutionServiceTests(TestCase):
    """The service scopes lookups to a visible recipe's own lines."""

    def setUp(self) -> None:
        self.author = create_user(username="subauthor")
        self.recipe = create_published_recipe(author=self.author, slug="sub-cake")
        add_ingredient(recipe=self.recipe, name="เนย", position=1)
        add_ingredient(recipe=self.recipe, name="Milk", position=2)
        add_ingredient(recipe=self.recipe, name="เกล็ดขนมปังพิเศษ", position=3)

    def test_known_substitutions_returned_in_display_order(self) -> None:
        results = substitution_service.for_recipe(slug="sub-cake")
        self.assertEqual(
            [r.normalized for r in results], ["เนย", "milk", "เกล็ดขนมปังพิเศษ"]
        )
        self.assertTrue(results[0].substitutions)
        self.assertEqual(results[0].substitutions[0].name, "มาการีน")

    def test_english_alias_resolves_to_same_rule(self) -> None:
        results = substitution_service.for_recipe(slug="sub-cake")
        milk = next(r for r in results if r.normalized == "milk")
        self.assertTrue(milk.substitutions)
        self.assertEqual(milk.substitutions[0].name, "นมถั่วเหลือง")

    def test_unknown_ingredient_yields_empty_candidates(self) -> None:
        results = substitution_service.for_recipe(slug="sub-cake")
        unknown = next(r for r in results if r.normalized == "เกล็ดขนมปังพิเศษ")
        self.assertEqual(unknown.substitutions, ())

    def test_ingredient_filter_normalizes_case_and_spacing(self) -> None:
        results = substitution_service.for_recipe(
            slug="sub-cake", ingredient="  MILK  "
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].normalized, "milk")

    def test_ingredient_filter_matches_across_languages(self) -> None:
        # "butter" and "เนย" fold to one canonical rule key, so an English
        # query finds the Thai line.
        results = substitution_service.for_recipe(
            slug="sub-cake", ingredient="Butter"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].normalized, "เนย")

    def test_ingredient_not_in_recipe_is_empty_not_error(self) -> None:
        results = substitution_service.for_recipe(
            slug="sub-cake", ingredient="น้ำตาลทราย"
        )
        self.assertEqual(results, [])

    def test_duplicate_lines_are_deduplicated(self) -> None:
        add_ingredient(recipe=self.recipe, name="เนย", position=4, group="ท็อปปิ้ง")
        results = substitution_service.for_recipe(slug="sub-cake")
        self.assertEqual(
            len([r for r in results if r.normalized == "เนย"]), 1
        )

    def test_deterministic_output(self) -> None:
        first = substitution_service.for_recipe(slug="sub-cake")
        second = substitution_service.for_recipe(slug="sub-cake")
        self.assertEqual(first, second)

    def test_hidden_recipe_raises_not_found(self) -> None:
        create_recipe(
            author=self.author,
            slug="sub-private",
            status=RecipeStatus.PUBLISHED,
            visibility=RecipeVisibility.PRIVATE,
        )
        with self.assertRaises(RecipeNotFoundError):
            substitution_service.for_recipe(slug="sub-private")

    def test_absent_recipe_raises_not_found(self) -> None:
        with self.assertRaises(RecipeNotFoundError):
            substitution_service.for_recipe(slug="no-such-recipe")

    def test_query_count_is_flat(self) -> None:
        add_ingredient(recipe=self.recipe, name="ไข่ไก่", position=5)
        with self.assertNumQueries(2):
            substitution_service.for_recipe(slug="sub-cake")


class SubstitutionApiTests(TestCase):
    """The endpoint is public, strict about input, and fails closed."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user(username="subapi")
        self.recipe = create_published_recipe(author=self.author, slug="sub-api")
        add_ingredient(recipe=self.recipe, name="Butter", position=1)

    def test_anonymous_read(self) -> None:
        response = self.client.get(url("sub-api"))
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(results[0]["ingredient"], "Butter")
        self.assertEqual(results[0]["normalized"], "butter")
        option = results[0]["substitutions"][0]
        self.assertEqual(
            sorted(option.keys()), ["confidence", "name", "note", "ratio"]
        )

    def test_ingredient_query_filters(self) -> None:
        add_ingredient(recipe=self.recipe, name="นมสด", position=2)
        response = self.client.get(url("sub-api"), {"ingredient": "butter"})
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["normalized"], "butter")

    def test_blank_ingredient_acts_as_no_filter(self) -> None:
        # DRF treats an empty value on a non-required query field as absent
        # (HTML-input semantics) — the same behavior as every other query
        # serializer in the project.
        response = self.client.get(url("sub-api"), {"ingredient": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)

    def test_overlong_ingredient_rejected(self) -> None:
        response = self.client.get(url("sub-api"), {"ingredient": "x" * 200})
        self.assertEqual(response.status_code, 400)

    def test_unknown_query_param_rejected(self) -> None:
        response = self.client.get(url("sub-api"), {"substitute": "x"})
        self.assertEqual(response.status_code, 400)

    def test_recipe_without_ingredients_returns_empty(self) -> None:
        create_published_recipe(author=self.author, slug="sub-empty")
        response = self.client.get(url("sub-empty"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_private_recipe_is_404_for_stranger_but_readable_by_owner(self) -> None:
        create_recipe(
            author=self.author,
            slug="sub-mine",
            status=RecipeStatus.PUBLISHED,
            visibility=RecipeVisibility.PRIVATE,
        )
        self.assertEqual(self.client.get(url("sub-mine")).status_code, 404)

        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url("sub-mine")).status_code, 200)

    def test_error_envelope_shape(self) -> None:
        response = self.client.get(url("no-such"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")
