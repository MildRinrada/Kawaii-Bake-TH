"""API tests for the staff category-curation endpoints."""

from __future__ import annotations

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.recipe_categories.models import RecipeCategory
from apps.users.tests.factories import create_user


def make_image_file(*, name: str = "tile.png") -> SimpleUploadedFile:
    """Build a real, decodable PNG upload."""
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color="pink").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


class AdminCategoryApiTests(TestCase):
    """/api/v1/admin/recipe-categories/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.list_url = reverse("recipe_categories_admin:list")

    def _detail_url(self, category_id: int) -> str:
        return reverse(
            "recipe_categories_admin:detail", kwargs={"category_id": category_id}
        )

    def test_every_route_requires_staff(self) -> None:
        existing = RecipeCategory.objects.first()
        cases = [
            (None, status.HTTP_401_UNAUTHORIZED),
            (self.member, status.HTTP_403_FORBIDDEN),
        ]
        for user, expected in cases:
            if user:
                self.client.force_login(user)
            self.assertEqual(self.client.get(self.list_url).status_code, expected)
            self.assertEqual(
                self.client.post(self.list_url, {"name": "x"}).status_code,
                expected,
            )
            self.assertEqual(
                self.client.patch(
                    self._detail_url(existing.id), {"name": "x"}
                ).status_code,
                expected,
            )
            self.assertEqual(
                self.client.delete(self._detail_url(existing.id)).status_code,
                expected,
            )
            self.client.logout()

    def test_admin_list_includes_inactive_categories(self) -> None:
        RecipeCategory.objects.create(
            name="เมนูลับ", slug="secret-menu", is_active=False
        )
        self.client.force_login(self.staff)

        rows = self.client.get(self.list_url).json()

        by_slug = {row["slug"]: row for row in rows}
        self.assertIn("secret-menu", by_slug)
        self.assertFalse(by_slug["secret-menu"]["is_active"])
        # The public list still hides it.
        public = self.client.get(reverse("recipe_categories:list")).json()
        self.assertNotIn("secret-menu", {row["slug"] for row in public})

    def test_create_derives_a_thai_slug_and_serves_the_image(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(
            self.list_url,
            {"name": "ขนมไทย", "image": make_image_file()},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertEqual(payload["slug"], "ขนมไทย")
        self.assertTrue(payload["image_url"].startswith("http"))

    def test_duplicate_slug_is_a_conflict(self) -> None:
        RecipeCategory.objects.create(name="Bread", slug="dup-bread")
        self.client.force_login(self.staff)

        response = self.client.post(
            self.list_url, {"name": "Other", "slug": "DUP-BREAD"}
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.json()["error"]["code"], "duplicate_category_slug"
        )

    def test_patch_edits_fields_and_clearing_image_removes_the_file(self) -> None:
        self.client.force_login(self.staff)
        created = self.client.post(
            self.list_url,
            {"name": "พายผลไม้", "image": make_image_file()},
            format="multipart",
        ).json()

        renamed = self.client.patch(
            self._detail_url(created["id"]),
            {"name": "พายผลไม้รวม", "display_order": 7},
            format="multipart",
        )
        self.assertEqual(renamed.status_code, status.HTTP_200_OK)
        self.assertEqual(renamed.json()["name"], "พายผลไม้รวม")
        self.assertEqual(renamed.json()["display_order"], 7)

        cleared = self.client.patch(
            self._detail_url(created["id"]),
            {"image": None},
            format="json",
        )
        self.assertEqual(cleared.status_code, status.HTTP_200_OK)
        self.assertIsNone(cleared.json()["image_url"])

    def test_garbage_image_bytes_are_rejected(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(
            self.list_url,
            {
                "name": "ปลอม",
                "image": SimpleUploadedFile(
                    "evil.png", b"not-an-image", content_type="image/png"
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_removes_the_category(self) -> None:
        target = RecipeCategory.objects.create(name="ชั่วคราว", slug="temporary")
        self.client.force_login(self.staff)

        response = self.client.delete(self._detail_url(target.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            RecipeCategory.objects.filter(slug="temporary").exists()
        )

    def test_unknown_category_is_a_404(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.patch(self._detail_url(999999), {"name": "x"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["error"]["code"], "category_not_found")
