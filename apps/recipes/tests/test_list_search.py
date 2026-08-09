"""Listing behaviour: filtering, ordering, pagination, search, query counts."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.recipes.constants import Difficulty, Ordering
from apps.recipes.tests.factories import (
    THAI_SEARCH_TERM,
    THAI_TITLE,
    add_ingredient,
    create_category,
    create_published_recipe,
)
from apps.users.tests.factories import create_user


class RecipeListQueryCountTests(TestCase):
    """The list endpoint must issue a constant number of queries.

    This is what replaces the safety a DTO would have given. It is the only
    thing that catches a future ``SerializerMethodField`` walking an
    un-prefetched relation, which is the banned lazy traversal.
    """

    def test_query_count_does_not_grow_with_result_count(self) -> None:
        author = create_user()
        category = create_category(slug="cake")
        for index in range(25):
            create_published_recipe(
                author=author, slug=f"recipe-{index}", categories=[category]
            )

        client = APIClient()
        # count + page rows + categories prefetch.
        with self.assertNumQueries(3):
            response = client.get(reverse("recipes:list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 20)


class RecipePaginationTests(TestCase):
    """Page-number pagination."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.author = create_user()
        for index in range(25):
            create_published_recipe(author=cls.author, slug=f"recipe-{index:02d}")

    def setUp(self) -> None:
        self.client = APIClient()

    def test_first_page_is_capped_at_the_page_size(self) -> None:
        response = self.client.get(reverse("recipes:list"))

        body = response.json()
        self.assertEqual(body["count"], 25)
        self.assertEqual(len(body["results"]), 20)
        self.assertIsNotNone(body["next"])
        self.assertIsNone(body["previous"])

    def test_second_page_returns_the_remainder(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"page": 2})

        self.assertEqual(len(response.json()["results"]), 5)

    def test_pages_do_not_overlap(self) -> None:
        # Guards the `-id` tiebreaker: without it, rows sharing a sort key
        # reshuffle between pages and users see duplicates and gaps.
        first = self.client.get(reverse("recipes:list"), {"page": 1}).json()["results"]
        second = self.client.get(reverse("recipes:list"), {"page": 2}).json()["results"]

        first_slugs = {item["slug"] for item in first}
        second_slugs = {item["slug"] for item in second}
        self.assertEqual(first_slugs & second_slugs, set())
        self.assertEqual(len(first_slugs | second_slugs), 25)

    def test_page_size_can_be_reduced(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"page_size": 5})

        self.assertEqual(len(response.json()["results"]), 5)

    def test_page_size_is_capped(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"page_size": 5000})

        self.assertLessEqual(len(response.json()["results"]), 100)

    def test_page_past_the_end_returns_404(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["error"]["code"], "not_found")


class RecipeFilterTests(TestCase):
    """Query-parameter filtering."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.author = create_user()
        cls.cake = create_category(slug="cake")
        cls.bread = create_category(slug="bread")

        cls.easy_cake = create_published_recipe(
            author=cls.author,
            slug="easy-cake",
            title="Easy Cake",
            categories=[cls.cake],
            difficulty=Difficulty.EASY,
            prep_minutes=5,
            cook_minutes=10,
        )
        cls.hard_bread = create_published_recipe(
            author=cls.author,
            slug="hard-bread",
            title="Hard Bread",
            categories=[cls.bread],
            difficulty=Difficulty.HARD,
            prep_minutes=60,
            cook_minutes=120,
        )
        add_ingredient(recipe=cls.hard_bread, name="Rye Flour")

    def setUp(self) -> None:
        self.client = APIClient()

    def _slugs(self, params: dict) -> set[str]:
        response = self.client.get(reverse("recipes:list"), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {item["slug"] for item in response.json()["results"]}

    def test_filter_by_category(self) -> None:
        self.assertEqual(self._slugs({"category": "cake"}), {"easy-cake"})

    def test_filter_by_multiple_categories(self) -> None:
        self.assertEqual(
            self._slugs({"category": "cake,bread"}), {"easy-cake", "hard-bread"}
        )

    def test_multi_category_filter_does_not_duplicate_rows(self) -> None:
        both = create_published_recipe(
            author=self.author, slug="both", categories=[self.cake, self.bread]
        )

        response = self.client.get(reverse("recipes:list"), {"category": "cake,bread"})

        slugs = [item["slug"] for item in response.json()["results"]]
        self.assertEqual(slugs.count(both.slug), 1)

    def test_filter_by_difficulty(self) -> None:
        self.assertEqual(self._slugs({"difficulty": "easy"}), {"easy-cake"})

    def test_filter_by_max_total_minutes(self) -> None:
        self.assertEqual(self._slugs({"max_total_minutes": 30}), {"easy-cake"})

    def test_filter_by_ingredient_uses_normalised_name(self) -> None:
        self.assertEqual(self._slugs({"ingredient": "  RYE   flour "}), {"hard-bread"})

    def test_filter_by_author(self) -> None:
        other = create_user()
        create_published_recipe(author=other, slug="someone-else")

        self.assertNotIn("someone-else", self._slugs({"author": self.author.username}))

    def test_unknown_category_yields_an_empty_page_not_an_error(self) -> None:
        # Categories are dynamic data; a bookmarked filter URL must not 400
        # when staff rename one. Assigning an unknown category IS a 400.
        response = self.client.get(reverse("recipes:list"), {"category": "nonexistent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 0)

    def test_unknown_difficulty_is_rejected(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"difficulty": "impossible"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_query_parameter_is_rejected(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"catgeory": "cake"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("catgeory", response.json()["error"]["details"])

    def test_unknown_ordering_is_rejected(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"ordering": "; DROP TABLE"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RecipeOrderingTests(TestCase):
    """Result ordering."""

    @classmethod
    def setUpTestData(cls) -> None:
        author = create_user()
        now = timezone.now()
        cls.old = create_published_recipe(
            author=author,
            slug="old",
            title="Alpha",
            published_at=now - timezone.timedelta(days=5),
            prep_minutes=100,
            cook_minutes=100,
            difficulty=Difficulty.HARD,
        )
        cls.new = create_published_recipe(
            author=author,
            slug="new",
            title="Zulu",
            published_at=now,
            prep_minutes=1,
            cook_minutes=1,
            difficulty=Difficulty.EASY,
        )

    def _order(self, ordering: str) -> list[str]:
        response = APIClient().get(reverse("recipes:list"), {"ordering": ordering})
        return [item["slug"] for item in response.json()["results"]]

    def test_newest_first_is_the_default(self) -> None:
        response = APIClient().get(reverse("recipes:list"))
        slugs = [item["slug"] for item in response.json()["results"]]

        self.assertEqual(slugs, ["new", "old"])

    def test_oldest_first(self) -> None:
        self.assertEqual(self._order(Ordering.OLDEST), ["old", "new"])

    def test_by_title(self) -> None:
        self.assertEqual(self._order(Ordering.TITLE), ["old", "new"])

    def test_quickest_first(self) -> None:
        self.assertEqual(self._order(Ordering.QUICKEST), ["new", "old"])

    def test_difficulty_uses_an_ordinal_not_alphabetical_order(self) -> None:
        # Alphabetically "hard" precedes "medium"; the ordinal must not.
        self.assertEqual(self._order(Ordering.DIFFICULTY), ["new", "old"])

    def test_popular_is_a_working_placeholder(self) -> None:
        # Maps to publication date until favourites exist. The API contract is
        # stable; only the ORDERING_MAP entry changes later.
        self.assertEqual(self._order(Ordering.POPULAR), ["new", "old"])


class RecipeSearchTests(TestCase):
    """GET /api/v1/recipes/search/"""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.author = create_user()
        cls.chocolate = create_published_recipe(
            author=cls.author, slug="choc", title="Chocolate Cake"
        )
        cls.thai = create_published_recipe(
            author=cls.author, slug="thai-croissant", title=THAI_TITLE
        )
        cls.plain = create_published_recipe(
            author=cls.author, slug="plain", title="Plain Scone"
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _search(self, term: str) -> set[str]:
        response = self.client.get(reverse("recipes:search"), {"q": term})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {item["slug"] for item in response.json()["results"]}

    def test_search_matches_title(self) -> None:
        self.assertEqual(self._search("chocolate"), {"choc"})

    def test_search_is_case_insensitive(self) -> None:
        self.assertEqual(self._search("CHOCOLATE"), {"choc"})

    def test_search_matches_thai_substring(self) -> None:
        # The Thai title has no spaces, so a substring match is the only thing
        # that can find it. This is why the Postgres backend is trigram-based
        # rather than tsvector-based.
        self.assertEqual(self._search(THAI_SEARCH_TERM), {"thai-croissant"})

    def test_search_excludes_non_matches(self) -> None:
        self.assertNotIn("plain", self._search("chocolate"))

    def test_search_requires_a_term(self) -> None:
        response = self.client.get(reverse("recipes:search"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_results_are_paginated(self) -> None:
        response = self.client.get(reverse("recipes:search"), {"q": "a"})

        self.assertIn("count", response.json())
        self.assertIn("results", response.json())

    def test_search_via_the_list_endpoint_also_works(self) -> None:
        response = self.client.get(reverse("recipes:list"), {"search": "chocolate"})

        slugs = {item["slug"] for item in response.json()["results"]}
        self.assertEqual(slugs, {"choc"})
