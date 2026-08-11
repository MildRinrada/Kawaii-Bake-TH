"""API tests for the staff recommendation-debug endpoints."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recipes.constants import RecipeStatus
from apps.recipes.tests.factories import create_recipe
from apps.users.tests.factories import create_user


class AdminRecommendationApiTests(TestCase):
    """/api/v1/admin/recommendations/…"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user(username="previewtarget")
        author = create_user()
        for _ in range(3):
            create_recipe(author=author, status=RecipeStatus.PUBLISHED)
        self.preview_url = reverse("recommendations_admin:preview")
        self.config_url = reverse("recommendations_admin:config")

    def test_both_routes_require_staff(self) -> None:
        for url in (self.preview_url, self.config_url):
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED
            )
        self.client.force_login(self.member)
        for url in (self.preview_url, self.config_url):
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_403_FORBIDDEN
            )

    def test_preview_returns_the_ranked_list_with_scores(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(
            self.preview_url, {"username": "previewtarget", "kind": "recipes"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["username"], "previewtarget")
        self.assertEqual(payload["kind"], "recipes")
        self.assertEqual(payload["count"], 3)
        first = payload["items"][0]
        self.assertEqual(first["rank"], 1)
        self.assertIsInstance(first["score"], float)
        self.assertIsInstance(first["reasons"], list)
        self.assertIsNotNone(first["title"])
        # The public feed still never carries a score.
        public = self.client.get("/api/v1/recommendations/recipes/").json()
        self.assertNotIn("score", public["results"][0])

    def test_preview_for_an_unknown_user_is_a_404(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.preview_url, {"username": "nobody"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_preview_requires_a_username(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.preview_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_config_exposes_the_deployed_weights(self) -> None:
        self.client.force_login(self.staff)

        payload = self.client.get(self.config_url).json()

        self.assertEqual(payload["candidate_pool_size"], 200)
        self.assertEqual(payload["w_author_affinity"], 3.0)
        self.assertEqual(payload["diversity_penalty"], 1.5)
