"""API tests for the staff favorites endpoints."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.tests.factories import create_course
from apps.favorites.tests.factories import create_favorite
from apps.recipes.tests.factories import create_recipe
from apps.users.tests.factories import create_user


class AdminFavoriteApiTests(TestCase):
    """GET /api/v1/admin/favorites/ and /top/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user(username="collectorbaker")
        self.other = create_user()
        self.recipe = create_recipe(author=create_user(), title="เค้กใบเตย")
        self.course = create_course(instructor=create_user())
        create_favorite(user=self.member, recipe=self.recipe)
        create_favorite(user=self.other, recipe=self.recipe)
        create_favorite(user=self.member, course=self.course)
        self.list_url = reverse("favorites_admin:list")
        self.top_url = reverse("favorites_admin:top")

    def test_both_routes_require_staff(self) -> None:
        for url in (self.list_url, self.top_url):
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED
            )
        self.client.force_login(self.member)
        for url in (self.list_url, self.top_url):
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_403_FORBIDDEN
            )

    def test_the_list_spans_users_and_carries_target_info(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        owners = {row["username"] for row in payload["results"]}
        self.assertEqual(owners, {"collectorbaker", self.other.username})
        recipe_rows = [
            row for row in payload["results"] if row["type"] == "recipe"
        ]
        self.assertEqual(recipe_rows[0]["target_title"], "เค้กใบเตย")
        self.assertEqual(recipe_rows[0]["target_slug"], self.recipe.slug)

    def test_type_and_search_filters_narrow_the_list(self) -> None:
        self.client.force_login(self.staff)

        courses_only = self.client.get(self.list_url, {"type": "course"}).json()
        self.assertEqual(courses_only["count"], 1)
        self.assertEqual(courses_only["results"][0]["type"], "course")

        by_title = self.client.get(self.list_url, {"search": "ใบเตย"}).json()
        self.assertEqual(by_title["count"], 2)

        by_owner = self.client.get(
            self.list_url, {"search": "collectorbaker"}
        ).json()
        self.assertEqual(by_owner["count"], 2)

    def test_top_ranks_by_favorite_count(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.top_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["recipes"][0]["id"], self.recipe.id)
        self.assertEqual(payload["recipes"][0]["count"], 2)
        self.assertEqual(payload["courses"][0]["count"], 1)
