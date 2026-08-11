"""API tests for the staff cross-user progress endpoints."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.progress.services import progress_service
from apps.users.tests.factories import create_user


class AdminProgressApiTests(TestCase):
    """/api/v1/admin/progress/…"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user(username="rosterlearner")
        self.instructor = create_user()
        self.course = create_published_course(
            instructor=self.instructor, title="คอร์สครัวซองต์"
        )
        self.lesson_one = create_lesson(course=self.course)
        self.lesson_two = create_lesson(course=self.course)
        enroll_user(user=self.member, course=self.course)
        progress_service.complete_lesson(
            user_id=self.member.id, lesson_id=self.lesson_one.id
        )

    def test_every_route_requires_staff(self) -> None:
        urls = [
            reverse("progress_admin:summary"),
            reverse("progress_admin:courses"),
            reverse(
                "progress_admin:enrollments", kwargs={"slug": self.course.slug}
            ),
        ]
        for url in urls:
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED
            )
        self.client.force_login(self.member)
        for url in urls:
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_403_FORBIDDEN
            )

    def test_summary_reports_real_platform_counters(self) -> None:
        self.client.force_login(self.staff)

        payload = self.client.get(reverse("progress_admin:summary")).json()

        self.assertEqual(payload["enrollments_total"], 1)
        self.assertEqual(payload["enrollments_active"], 1)
        self.assertEqual(payload["learners"], 1)
        self.assertEqual(payload["lessons_completed"], 1)
        self.assertEqual(payload["active_learners_7d"], 1)

    def test_course_stats_show_the_enrollment_funnel(self) -> None:
        dropped = create_user()
        enroll_user(user=dropped, course=self.course, status="dropped")
        self.client.force_login(self.staff)

        rows = self.client.get(reverse("progress_admin:courses")).json()[
            "results"
        ]

        row = next(r for r in rows if r["slug"] == self.course.slug)
        self.assertEqual(row["enrolled_count"], 2)
        self.assertEqual(row["active_count"], 1)
        self.assertEqual(row["dropped_count"], 1)
        self.assertEqual(row["completion_rate"], 0)
        self.assertEqual(row["published_lesson_count"], 2)

    def test_roster_merges_per_learner_progress(self) -> None:
        self.client.force_login(self.staff)

        payload = self.client.get(
            reverse(
                "progress_admin:enrollments", kwargs={"slug": self.course.slug}
            )
        ).json()

        row = payload["results"][0]
        self.assertEqual(row["username"], "rosterlearner")
        self.assertEqual(row["completed_lessons"], 1)
        self.assertEqual(row["total_lessons"], 2)
        self.assertEqual(row["percent"], 50)
        self.assertIsNotNone(row["last_activity_at"])
        self.assertEqual(row["status"], "active")

    def test_roster_filters_by_status_and_search(self) -> None:
        other = create_user(username="quietbaker")
        enroll_user(user=other, course=self.course, status="dropped")
        self.client.force_login(self.staff)
        url = reverse(
            "progress_admin:enrollments", kwargs={"slug": self.course.slug}
        )

        dropped_only = self.client.get(url, {"status": "dropped"}).json()
        self.assertEqual(
            [row["username"] for row in dropped_only["results"]], ["quietbaker"]
        )

        by_name = self.client.get(url, {"search": "rosterlearner"}).json()
        self.assertEqual(by_name["count"], 1)

    def test_unknown_course_is_a_404(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("progress_admin:enrollments", kwargs={"slug": "no-course"})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
