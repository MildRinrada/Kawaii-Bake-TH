"""Favorites: idempotent toggles and the visibility-filtered list."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.courses.constants import CourseStatus
from apps.courses.tests.factories import create_published_course, enroll_user
from apps.favorites.exceptions import FavoriteTargetNotFoundError
from apps.favorites.models import Favorite
from apps.favorites.services import favorite_service
from apps.favorites.tests.factories import create_favorite
from apps.recipes.constants import RecipeVisibility
from apps.recipes.models import Recipe
from apps.recipes.tests.factories import create_published_recipe
from apps.users.tests.factories import create_user

FAVORITES_URL = "/api/v1/users/me/favorites/"


class FavoriteServiceTests(TestCase):
    """Toggle semantics mirror enrollment: idempotent both ways."""

    def setUp(self) -> None:
        self.author = create_user(username="fvauthor")
        self.user = create_user(username="fvuser")
        self.recipe = create_published_recipe(author=self.author, slug="fv-bread")

    def test_favorite_is_idempotent(self) -> None:
        _, created = favorite_service.favorite(
            user_id=self.user.id, kind="recipe", slug="fv-bread"
        )
        self.assertTrue(created)
        _, created = favorite_service.favorite(
            user_id=self.user.id, kind="recipe", slug="fv-bread"
        )
        self.assertFalse(created)
        self.assertEqual(Favorite.objects.count(), 1)

    def test_unfavorite_is_idempotent(self) -> None:
        favorite_service.favorite(user_id=self.user.id, kind="recipe", slug="fv-bread")
        favorite_service.unfavorite(
            user_id=self.user.id, kind="recipe", slug="fv-bread"
        )
        favorite_service.unfavorite(
            user_id=self.user.id, kind="recipe", slug="fv-bread"
        )
        self.assertEqual(Favorite.objects.count(), 0)

    def test_hidden_target_cannot_be_favorited(self) -> None:
        Recipe.objects.filter(pk=self.recipe.pk).update(
            visibility=RecipeVisibility.PRIVATE
        )
        with self.assertRaises(FavoriteTargetNotFoundError):
            favorite_service.favorite(
                user_id=self.user.id, kind="recipe", slug="fv-bread"
            )

    def test_own_content_is_favoritable(self) -> None:
        _, created = favorite_service.favorite(
            user_id=self.author.id, kind="recipe", slug="fv-bread"
        )
        self.assertTrue(created)


class FavoritesListTests(TestCase):
    """The list follows the detail visibility rule via prefix Q builders."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user(username="flauthor")
        self.user = create_user(username="fluser")
        self.recipe = create_published_recipe(author=self.author, slug="fl-bread")
        self.course = create_published_course(instructor=self.author, slug="fl-course")
        create_favorite(user=self.user, recipe=self.recipe)
        create_favorite(user=self.user, course=self.course)

    def test_anonymous_is_401(self) -> None:
        self.assertEqual(self.client.get(FAVORITES_URL).status_code, 401)

    def test_list_embeds_both_card_kinds(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(FAVORITES_URL)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        by_type = {item["type"]: item for item in payload["results"]}
        self.assertEqual(by_type["recipe"]["recipe"]["slug"], "fl-bread")
        self.assertIsNone(by_type["recipe"]["course"])
        self.assertEqual(by_type["course"]["course"]["slug"], "fl-course")

    def test_type_filter_narrows(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(FAVORITES_URL, {"type": "course"})
        self.assertEqual(response.json()["count"], 1)

    def test_hidden_target_leaves_the_list_silently(self) -> None:
        Recipe.objects.filter(pk=self.recipe.pk).update(
            visibility=RecipeVisibility.PRIVATE
        )
        self.client.force_login(self.user)
        payload = self.client.get(FAVORITES_URL).json()

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["type"], "course")
        # The row itself survives  the bookmark returns if the recipe does.
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 2)

    def test_archived_course_stays_for_the_enrolled_student(self) -> None:
        enroll_user(user=self.user, course=self.course)
        self.course.status = CourseStatus.ARCHIVED
        self.course.save(update_fields=["status"])

        self.client.force_login(self.user)
        payload = self.client.get(FAVORITES_URL, {"type": "course"}).json()

        self.assertEqual(payload["count"], 1)

    def test_toggle_endpoints_roundtrip(self) -> None:
        other = create_published_recipe(author=self.author, slug="fl-cake")
        self.client.force_login(self.user)

        first = self.client.post(f"/api/v1/recipes/{other.slug}/favorite/")
        again = self.client.post(f"/api/v1/recipes/{other.slug}/favorite/")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(again.status_code, 200)

        removed = self.client.delete(f"/api/v1/recipes/{other.slug}/favorite/")
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(
            Favorite.objects.filter(user=self.user, recipe=other).exists()
        )
