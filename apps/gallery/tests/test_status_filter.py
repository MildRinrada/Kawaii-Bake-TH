"""Tests for the gallery list's status filter.

The filter intersects the visibility rule, so it narrows what a viewer
could already see and can never widen it - the property these tests pin.
"""

from __future__ import annotations

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.gallery.constants import GalleryPostStatus
from apps.gallery.tests.factories import create_post
from apps.users.tests.factories import create_user

GALLERY_URL = "/api/v1/gallery/"


class GalleryStatusFilterTests(TestCase):
    """GET /api/v1/gallery/?status=…"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user()
        self.staff = create_user(is_staff=True)
        self.published = create_post(author=self.author)
        self.hidden = create_post(
            author=self.author, status=GalleryPostStatus.UNPUBLISHED
        )

    def test_staff_can_isolate_the_moderation_queue(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(GALLERY_URL, {"status": "unpublished"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["results"]
        self.assertEqual([row["id"] for row in rows], [self.hidden.id])

    def test_the_owner_can_isolate_their_own_hidden_posts(self) -> None:
        self.client.force_login(self.author)

        rows = self.client.get(
            GALLERY_URL, {"status": "unpublished"}
        ).json()["results"]

        self.assertEqual([row["id"] for row in rows], [self.hidden.id])

    def test_the_filter_never_widens_for_strangers(self) -> None:
        stranger = create_user()
        self.client.force_login(stranger)

        rows = self.client.get(
            GALLERY_URL, {"status": "unpublished"}
        ).json()["results"]

        self.assertEqual(rows, [])

    def test_garbage_status_values_are_ignored(self) -> None:
        response = self.client.get(GALLERY_URL, {"status": "nonsense"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["results"]
        self.assertEqual([row["id"] for row in rows], [self.published.id])
