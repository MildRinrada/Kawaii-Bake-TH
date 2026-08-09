"""Tests for gallery image uploads and nutrition round-tripping."""

from __future__ import annotations

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.recipes.constants import MAX_IMAGES_PER_RECIPE, NutritionSource
from apps.recipes.models import Nutrition, RecipeImage
from apps.recipes.services import recipe_service
from apps.recipes.tests.factories import create_category, create_recipe
from apps.users.tests.factories import create_user


def make_image_file(
    *, name: str = "bake.png", image_format: str = "PNG", size: tuple[int, int] = (10, 10)
) -> SimpleUploadedFile:
    """Build a real, decodable image upload."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color="white").save(buffer, format=image_format)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


class RecipeImageApiTests(TestCase):
    """POST/DELETE /api/v1/recipes/{slug}/images/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.owner = create_user()
        self.stranger = create_user()
        self.recipe = create_recipe(author=self.owner, slug="cake")
        self.url = reverse("recipes:image_create", kwargs={"slug": "cake"})

    def test_owner_can_upload(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            self.url, {"image": make_image_file(), "caption": "Fresh out of the oven"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.json()["image_url"])
        self.assertEqual(RecipeImage.objects.filter(recipe=self.recipe).count(), 1)

    def test_anonymous_cannot_upload(self) -> None:
        response = self.client.post(self.url, {"image": make_image_file()})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stranger_cannot_upload(self) -> None:
        self.client.force_login(self.stranger)

        response = self.client.post(self.url, {"image": make_image_file()})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_image_payload_is_rejected(self) -> None:
        self.client.force_login(self.owner)
        fake = SimpleUploadedFile("evil.png", b"not-an-image", content_type="image/png")

        response = self.client.post(self.url, {"image": fake})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_svg_is_rejected(self) -> None:
        # SVG can carry script; accepting it would be stored XSS.
        self.client.force_login(self.owner)
        svg = SimpleUploadedFile(
            "x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            content_type="image/svg+xml",
        )

        response = self.client.post(self.url, {"image": svg})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gallery_capacity_is_enforced(self) -> None:
        self.client.force_login(self.owner)
        for _ in range(MAX_IMAGES_PER_RECIPE):
            RecipeImage.objects.create(recipe=self.recipe, image="recipes/x.png")

        response = self.client.post(self.url, {"image": make_image_file()})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_uploaded_filename_is_not_reused(self) -> None:
        # The client filename must never reach the storage path.
        self.client.force_login(self.owner)

        self.client.post(self.url, {"image": make_image_file(name="../../evil.png")})

        stored = RecipeImage.objects.get(recipe=self.recipe)
        self.assertNotIn("evil", stored.image.name)
        self.assertNotIn("..", stored.image.name)

    def test_owner_can_delete_an_image(self) -> None:
        self.client.force_login(self.owner)
        created = self.client.post(self.url, {"image": make_image_file()}).json()

        response = self.client.delete(
            reverse(
                "recipes:image_delete",
                kwargs={"slug": "cake", "image_id": created["id"]},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RecipeImage.objects.filter(recipe=self.recipe).count(), 0)

    def test_cannot_delete_an_image_from_another_recipe(self) -> None:
        other = create_recipe(author=self.stranger, slug="other")
        foreign = RecipeImage.objects.create(recipe=other, image="recipes/x.png")
        self.client.force_login(self.owner)

        response = self.client.delete(
            reverse(
                "recipes:image_delete",
                kwargs={"slug": "cake", "image_id": foreign.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(RecipeImage.objects.filter(pk=foreign.pk).exists())


class NutritionTests(TestCase):
    """Nutrition is stored and echoed back, never computed."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user()
        create_category(slug="cake")

    def _create(self, nutrition: dict | None) -> dict:
        self.client.force_login(self.user)
        payload = {
            "title": "Nutrition Cake",
            "category_slugs": ["cake"],
            "ingredients": [{"name": "Sugar", "quantity": "50.000", "unit": "g"}],
            "steps": [{"body": "Bake."}],
        }
        if nutrition is not None:
            payload["nutrition"] = nutrition
        response = self.client.post(reverse("recipes:list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()

    def test_recipe_without_nutrition_returns_null(self) -> None:
        body = self._create(None)

        self.assertIsNone(body["nutrition"])
        self.assertEqual(Nutrition.objects.count(), 0)

    def test_nutrition_round_trips_verbatim(self) -> None:
        body = self._create({"calories_kcal": "321.50", "protein_g": "4.25"})

        self.assertEqual(body["nutrition"]["calories_kcal"], "321.50")
        self.assertEqual(body["nutrition"]["protein_g"], "4.25")

    def test_source_is_always_manual_in_phase_2(self) -> None:
        body = self._create({"calories_kcal": "100.00"})

        self.assertEqual(body["nutrition"]["source"], NutritionSource.MANUAL)

    def test_nothing_is_computed_from_ingredients(self) -> None:
        # Phase 2 performs zero arithmetic: unsupplied figures stay unknown.
        body = self._create({"calories_kcal": "100.00"})

        self.assertIsNone(body["nutrition"]["protein_g"])

    def test_negative_value_is_rejected(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("recipes:list"),
            {
                "title": "Bad Nutrition",
                "nutrition": {"calories_kcal": "-5.00"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nutrition_can_be_cleared(self) -> None:
        created = self._create({"calories_kcal": "100.00"})

        response = self.client.patch(
            reverse("recipes:detail", kwargs={"slug": created["slug"]}),
            {"nutrition": None},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["nutrition"])

    def test_service_upsert_is_idempotent(self) -> None:
        recipe = create_recipe(author=self.user)

        recipe_service.update_recipe(
            slug=recipe.slug,
            viewer_id=self.user.id,
            data={"nutrition": {"calories_kcal": 100}},
        )
        recipe_service.update_recipe(
            slug=recipe.slug,
            viewer_id=self.user.id,
            data={"nutrition": {"calories_kcal": 200}},
        )

        self.assertEqual(Nutrition.objects.filter(recipe=recipe).count(), 1)
