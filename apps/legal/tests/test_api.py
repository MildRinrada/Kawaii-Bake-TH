"""API tests for the legal-document endpoints."""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.legal.models import LegalDocument
from apps.users.tests.factories import create_user

ALL_KINDS = {"terms", "privacy", "pdpa", "cookie"}


class LegalReadApiTests(TestCase):
    """GET /api/v1/legal/ and /api/v1/legal/{kind}/"""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()

    def test_the_four_seeded_documents_are_listed_publicly(self) -> None:
        response = self.client.get(reverse("legal:list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()
        self.assertEqual({row["kind"] for row in rows}, ALL_KINDS)
        # The list is metadata only  bodies can be long.
        self.assertNotIn("body", rows[0])

    def test_detail_serves_the_full_text_to_anonymous(self) -> None:
        response = self.client.get(
            reverse("legal:detail", kwargs={"kind": "terms"})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["kind"], "terms")
        self.assertEqual(payload["version"], 1)
        self.assertIn("ข้อตกลง", payload["body"])

    def test_an_unknown_kind_is_a_404(self) -> None:
        response = self.client.get(
            reverse("legal:detail", kwargs={"kind": "nonsense"})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json()["error"]["code"], "legal_document_not_found"
        )


class LegalEditApiTests(TestCase):
    """PATCH /api/v1/legal/{kind}/"""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.url = reverse("legal:detail", kwargs={"kind": "cookie"})

    def test_editing_requires_staff(self) -> None:
        cases = [
            (None, status.HTTP_401_UNAUTHORIZED),
            (self.member, status.HTTP_403_FORBIDDEN),
        ]
        for user, expected in cases:
            if user:
                self.client.force_login(user)
            response = self.client.patch(
                self.url, {"body": "new text"}, format="json"
            )
            self.assertEqual(response.status_code, expected)
            self.client.logout()

        # Nothing changed while unauthorised callers were knocking.
        document = LegalDocument.objects.get(kind="cookie")
        self.assertEqual(document.version, 1)

    def test_staff_edit_updates_and_bumps_the_version(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.patch(
            self.url,
            {"title": "นโยบายคุกกี้ (แก้ไข)", "body": "ฉบับปรับปรุง"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["title"], "นโยบายคุกกี้ (แก้ไข)")
        self.assertEqual(payload["body"], "ฉบับปรับปรุง")
        self.assertEqual(payload["version"], 2)

        # The public read serves the new text immediately.
        public = APIClient().get(self.url)
        self.assertEqual(public.json()["body"], "ฉบับปรับปรุง")

    def test_a_partial_edit_keeps_the_other_field(self) -> None:
        self.client.force_login(self.staff)
        original_title = LegalDocument.objects.get(kind="cookie").title

        response = self.client.patch(self.url, {"body": "เฉพาะเนื้อหา"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["title"], original_title)
        self.assertEqual(response.json()["version"], 2)

    def test_an_empty_patch_is_rejected(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.patch(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # And the version did not budge  a no-op must not look like an edit.
        self.assertEqual(LegalDocument.objects.get(kind="cookie").version, 1)

    def test_unknown_keys_are_rejected(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.patch(
            self.url, {"body": "x", "is_published": False}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_published", response.json()["error"]["details"])

    def test_concurrent_edits_both_bump_the_version(self) -> None:
        # The F-expression increment means no lost update.
        self.client.force_login(self.staff)
        self.client.patch(self.url, {"body": "หนึ่ง"}, format="json")
        response = self.client.patch(self.url, {"body": "สอง"}, format="json")

        self.assertEqual(response.json()["version"], 3)
