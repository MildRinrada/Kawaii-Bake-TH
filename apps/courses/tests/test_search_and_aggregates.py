"""Course list search and the aggregate columns on the list payload."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.constants import CourseStatus, CourseVisibility
from apps.courses.tests.factories import create_course
from apps.users.tests.factories import create_user


class CourseSearchApiTests(TestCase):
    """GET /api/v1/courses/?search="""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("courses:list")
        self.instructor = create_user(
            email="teacher@example.com", username="teacher"
        )
        self.bread = create_course(
            instructor=self.instructor,
            title="ขนมปังโฮลวีตเบื้องต้น",
            summary="เรียนอบขนมปังเพื่อสุขภาพ",
            description="ครอบคลุมการนวดและการหมักยีสต์",
            status=CourseStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        self.cake = create_course(
            instructor=self.instructor,
            title="แต่งหน้าเค้กด้วยครีม",
            summary="บีบดอกไม้และปาดหน้า",
            status=CourseStatus.PUBLISHED,
            published_at=timezone.now(),
        )

    def _titles(self, **params: str) -> list[str]:
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [row["title"] for row in response.json()["results"]]

    def test_search_matches_title(self) -> None:
        self.assertEqual(self._titles(search="ขนมปัง"), [self.bread.title])

    def test_search_matches_summary(self) -> None:
        self.assertEqual(self._titles(search="บีบดอกไม้"), [self.cake.title])

    def test_search_matches_description(self) -> None:
        self.assertEqual(self._titles(search="การหมักยีสต์"), [self.bread.title])

    def test_search_miss_returns_empty(self) -> None:
        self.assertEqual(self._titles(search="ซาวร์โดว์"), [])

    def test_search_combines_with_difficulty(self) -> None:
        titles = self._titles(search="เค้ก", difficulty="beginner")
        self.assertEqual(titles, [self.cake.title])

    def test_search_does_not_reveal_hidden_courses(self) -> None:
        create_course(
            instructor=self.instructor,
            title="ขนมปังลับเฉพาะ",
            status=CourseStatus.PUBLISHED,
            visibility=CourseVisibility.PRIVATE,
            published_at=timezone.now(),
        )
        create_course(instructor=self.instructor, title="ขนมปังฉบับร่าง")

        self.assertEqual(self._titles(search="ขนมปัง"), [self.bread.title])


class CourseListAggregateFieldTests(TestCase):
    """The list payload carries the stored aggregates — no extra queries."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("courses:list")
        instructor = create_user(email="t2@example.com", username="teachertwo")
        self.course = create_course(
            instructor=instructor,
            status=CourseStatus.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_unreviewed_course_has_null_average_and_zero_count(self) -> None:
        row = self.client.get(self.url).json()["results"][0]

        self.assertIsNone(row["rating_average"])
        self.assertEqual(row["rating_count"], 0)
        self.assertEqual(row["total_duration_minutes"], 0)

    def test_stored_aggregates_are_serialized(self) -> None:
        self.course.rating_average = "4.50"
        self.course.rating_count = 2
        self.course.published_duration_minutes = 95
        self.course.save()

        row = self.client.get(self.url).json()["results"][0]

        self.assertEqual(row["rating_average"], 4.5)
        self.assertEqual(row["rating_count"], 2)
        self.assertEqual(row["total_duration_minutes"], 95)
