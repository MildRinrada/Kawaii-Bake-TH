"""API tests for the staff flat review list."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.tests.factories import create_course
from apps.recipes.tests.factories import create_recipe
from apps.reviews.constants import ReviewStatus
from apps.reviews.tests.factories import create_review
from apps.users.tests.factories import create_user


class AdminReviewListApiTests(TestCase):
    """GET /api/v1/admin/reviews/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user(username="flatlistfan")
        self.recipe = create_recipe(author=create_user())
        self.course = create_course(instructor=create_user())
        self.active = create_review(
            user=self.member, recipe=self.recipe, rating=5
        )
        self.hidden = create_review(
            user=create_user(),
            course=self.course,
            rating=2,
            status=ReviewStatus.HIDDEN,
        )
        self.deleted = create_review(
            user=create_user(),
            recipe=self.recipe,
            rating=1,
            status=ReviewStatus.DELETED,
        )
        self.url = reverse("reviews_admin:list")

    def test_the_list_requires_staff(self) -> None:
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_the_default_view_spans_targets_but_hides_tombstones(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["results"]
        ids = {row["id"] for row in rows}
        self.assertEqual(ids, {self.active.id, self.hidden.id})
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id[self.active.id]["recipe_title"], self.recipe.title)
        self.assertEqual(by_id[self.hidden.id]["course_title"], self.course.title)

    def test_filters_narrow_by_status_target_rating_and_search(self) -> None:
        self.client.force_login(self.staff)

        deleted_only = self.client.get(self.url, {"status": "deleted"}).json()
        self.assertEqual(
            [row["id"] for row in deleted_only["results"]], [self.deleted.id]
        )

        courses_only = self.client.get(self.url, {"target": "course"}).json()
        self.assertEqual(
            [row["id"] for row in courses_only["results"]], [self.hidden.id]
        )

        five_stars = self.client.get(self.url, {"rating": 5}).json()
        self.assertEqual(
            [row["id"] for row in five_stars["results"]], [self.active.id]
        )

        by_author = self.client.get(self.url, {"search": "flatlistfan"}).json()
        self.assertEqual(
            [row["id"] for row in by_author["results"]], [self.active.id]
        )

    def test_an_unknown_filter_is_rejected(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.url, {"stars": 5})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
