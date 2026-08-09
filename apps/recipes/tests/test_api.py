"""API tests for the recipe endpoints."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recipes.constants import RecipeStatus, RecipeVisibility
from apps.recipes.models import Recipe
from apps.recipes.tests.factories import (
    THAI_TITLE,
    create_category,
    create_published_recipe,
    create_recipe,
    make_publishable,
)
from apps.users.tests.factories import create_user


class RecipeCreateApiTests(TestCase):
    """POST /api/v1/recipes/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user()
        create_category(slug="cake")
        self.url = reverse("recipes:list")

    def _payload(self, **overrides) -> dict:
        payload = {
            "title": "Chocolate Brownie",
            "summary": "Fudgy.",
            "prep_minutes": 15,
            "cook_minutes": 30,
            "servings": 8,
            "category_slugs": ["cake"],
            "ingredients": [{"name": "Butter", "quantity": "200.000", "unit": "g"}],
            "steps": [{"body": "Melt the butter."}],
        }
        payload.update(overrides)
        return payload

    def test_anonymous_cannot_create(self) -> None:
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_returns_the_full_detail_payload(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["title"], "Chocolate Brownie")
        self.assertEqual(body["status"], RecipeStatus.DRAFT)
        self.assertEqual(len(body["ingredients"]), 1)
        self.assertEqual(len(body["steps"]), 1)
        self.assertEqual(body["total_minutes"], 45)

    def test_create_rejects_unknown_field(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, self._payload(titel="typo"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("titel", response.json()["error"]["details"])

    def test_create_cannot_set_status(self) -> None:
        # `status` is not on the create serializer, so a client cannot publish
        # around the completeness checks.
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, self._payload(status="published"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_unknown_category(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, self._payload(category_slugs=["nope"]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"]["code"], "invalid_category")

    def test_create_rejects_invalid_servings(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, self._payload(servings=0), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_accepts_a_thai_title(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, self._payload(title=THAI_TITLE), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response.json()["slug"], "")


class RecipeDetailApiTests(TestCase):
    """GET/PATCH/DELETE /api/v1/recipes/{slug}/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.owner = create_user()
        self.stranger = create_user()
        self.recipe = create_published_recipe(author=self.owner, slug="brownie")

    def _url(self, slug: str = "brownie") -> str:
        return reverse("recipes:detail", kwargs={"slug": slug})

    def test_anonymous_can_read_published_public(self) -> None:
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["slug"], "brownie")

    def test_detail_payload_has_the_expected_keys(self) -> None:
        response = self.client.get(self._url())

        self.assertEqual(
            set(response.json()),
            {
                "id",
                "slug",
                "title",
                "summary",
                "description",
                "difficulty",
                "prep_minutes",
                "cook_minutes",
                "total_minutes",
                "servings",
                "status",
                "visibility",
                "published_at",
                "created_at",
                "cover_image_url",
                "author",
                "categories",
                "ingredients",
                "steps",
                "images",
                "nutrition",
            },
        )

    def test_payload_carries_the_primary_key_other_apps_write_with(self) -> None:
        # The gallery post attachment takes a `recipe_id`; without this
        # field a client has no way to turn a browsed recipe into one
        # (ADR 0023). The same value is already public in gallery and Q&A
        # reference cards, so this discloses nothing new.
        response = self.client.get(self._url())

        self.assertEqual(response.json()["id"], self.recipe.pk)

    def test_owner_can_patch(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.patch(
            self._url(), {"summary": "Even fudgier."}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["summary"], "Even fudgier.")

    def test_stranger_patch_returns_404(self) -> None:
        self.client.force_login(self.stranger)

        response = self.client.patch(self._url(), {"summary": "Mine now."}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_patch_returns_401(self) -> None:
        response = self.client.patch(self._url(), {"summary": "Nope."}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_cannot_change_published_slug(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.patch(self._url(), {"slug": "renamed"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "slug_immutable")

    def test_owner_can_delete(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.delete(self._url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(slug="brownie").exists())

    def test_stranger_delete_returns_404(self) -> None:
        self.client.force_login(self.stranger)

        response = self.client.delete(self._url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(slug="brownie").exists())

    def test_reserved_route_is_not_shadowed_by_a_slug(self) -> None:
        # `search` is a literal route declared before <str:slug>.
        create_published_recipe(author=self.owner, slug="search-alike")

        response = self.client.get(reverse("recipes:search"), {"q": "brownie"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.json())


class RecipeLifecycleApiTests(TestCase):
    """POST publish / unpublish / archive."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.owner = create_user()
        self.recipe = create_recipe(author=self.owner, slug="cake")

    def test_publishing_incomplete_recipe_returns_a_checklist(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("recipes:publish", kwargs={"slug": "cake"})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.json()["error"]
        self.assertEqual(body["code"], "recipe_not_publishable")
        # Every problem at once, so the UI can render a checklist.
        self.assertGreaterEqual(len(body["details"]), 4)

    def test_publish_then_unpublish_then_archive(self) -> None:
        make_publishable(self.recipe)
        self.client.force_login(self.owner)

        published = self.client.post(reverse("recipes:publish", kwargs={"slug": "cake"}))
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertEqual(published.json()["status"], RecipeStatus.PUBLISHED)

        unpublished = self.client.post(
            reverse("recipes:unpublish", kwargs={"slug": "cake"})
        )
        self.assertEqual(unpublished.json()["status"], RecipeStatus.DRAFT)

        archived = self.client.post(reverse("recipes:archive", kwargs={"slug": "cake"}))
        self.assertEqual(archived.json()["status"], RecipeStatus.ARCHIVED)

    def test_stranger_cannot_publish(self) -> None:
        make_publishable(self.recipe)
        self.client.force_login(create_user())

        response = self.client.post(reverse("recipes:publish", kwargs={"slug": "cake"}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_publish(self) -> None:
        response = self.client.post(reverse("recipes:publish", kwargs={"slug": "cake"}))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CategoryApiTests(TestCase):
    """GET /api/v1/recipe-categories/"""

    def setUp(self) -> None:
        self.client = APIClient()

    def test_categories_are_public(self) -> None:
        response = self.client.get(reverse("recipe_categories:list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {item["slug"] for item in response.json()}
        self.assertIn("cake", slugs)

    def test_counts_only_publicly_visible_recipes(self) -> None:
        category = create_category(slug="cake")
        author = create_user()
        create_published_recipe(author=author, categories=[category])
        create_recipe(author=author, categories=[category])  # draft
        create_published_recipe(
            author=author, categories=[category], visibility=RecipeVisibility.PRIVATE
        )

        response = self.client.get(reverse("recipe_categories:list"))

        entry = next(item for item in response.json() if item["slug"] == "cake")
        self.assertEqual(entry["recipe_count"], 1)

    def test_inactive_categories_are_hidden(self) -> None:
        create_category(slug="secret-category", is_active=False)

        response = self.client.get(reverse("recipe_categories:list"))

        slugs = {item["slug"] for item in response.json()}
        self.assertNotIn("secret-category", slugs)
