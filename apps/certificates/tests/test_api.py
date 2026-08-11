"""API tests: the endpoint surface, the public verification, no N+1."""

from __future__ import annotations

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.certificates.models import BadgeDefinition
from apps.certificates.services import certificate_service
from apps.certificates.tests.factories import build_completed_course
from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.users.tests.factories import create_user


class CertificateApiTests(TestCase):
    """Issue, list, verify  with the permission split."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.student = create_user(username="capistudent")
        self.instructor = create_user(username="capiinst")

    def test_anonymous_is_denied_on_owner_endpoints(self) -> None:
        paths = [
            ("post", "/api/v1/courses/some-course/certificate/"),
            ("get", "/api/v1/me/certificates/"),
            ("get", "/api/v1/me/achievements/"),
        ]
        for method, path in paths:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)

    def test_issue_gate_codes(self) -> None:
        course = create_published_course(
            instructor=self.instructor, slug="capi-gate"
        )
        create_lesson(course=course)
        self.client.force_login(self.student)

        not_enrolled = self.client.post("/api/v1/courses/capi-gate/certificate/")
        self.assertEqual(not_enrolled.status_code, 403)
        self.assertEqual(
            not_enrolled.json()["error"]["code"], "enrollment_required"
        )

        enroll_user(user=self.student, course=course)
        incomplete = self.client.post("/api/v1/courses/capi-gate/certificate/")
        self.assertEqual(incomplete.status_code, 409)
        self.assertEqual(
            incomplete.json()["error"]["code"], "course_not_completed"
        )

        missing = self.client.post("/api/v1/courses/no-such-course/certificate/")
        self.assertEqual(missing.status_code, 404)

    def test_issue_then_idempotent_reissue(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        self.client.force_login(self.student)

        first = self.client.post(f"/api/v1/courses/{course.slug}/certificate/")
        second = self.client.post(f"/api/v1/courses/{course.slug}/certificate/")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            first.json()["certificate_number"],
            second.json()["certificate_number"],
        )
        self.assertEqual(first.json()["status"], "valid")
        self.assertEqual(first.json()["course_title"], course.title)

    def test_my_certificates_lists_only_mine_with_flat_queries(self) -> None:
        for _ in range(3):
            course = build_completed_course(
                student=self.student, instructor=self.instructor
            )
            certificate_service.issue_if_completed(
                user_id=self.student.id, course_slug=course.slug
            )
        other = create_user(username="capiother")
        other_course = build_completed_course(
            student=other, instructor=self.instructor
        )
        certificate_service.issue_if_completed(
            user_id=other.id, course_slug=other_course.slug
        )

        self.client.force_login(self.student)
        # session + user + count + page  snapshots keep the list join-free.
        with self.assertNumQueries(4):
            response = self.client.get("/api/v1/me/certificates/")
        self.assertEqual(response.json()["count"], 3)

    def test_anonymous_verification_shows_public_record_only(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        certificate, _ = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

        response = self.client.get(
            f"/api/v1/certificates/{certificate.verification_token}/"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "valid")
        self.assertEqual(body["student_name"], self.student.username)
        self.assertEqual(body["course_title"], course.title)
        # Never the email, never internal ids.
        self.assertNotIn("email", body)
        self.assertNotIn("id", body)
        self.assertNotIn(self.student.email, str(body))

    def test_verification_reports_revoked(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        certificate, _ = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )
        certificate_service.revoke(
            certificate_id=certificate.pk, user_id=self.student.id
        )

        response = self.client.get(
            f"/api/v1/certificates/{certificate.verification_token}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "revoked")

    def test_unknown_token_is_404(self) -> None:
        response = self.client.get(f"/api/v1/certificates/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, 404)

    def test_my_achievements_come_with_badges(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

        self.client.force_login(self.student)
        # session + user + count + page (badge via select_related).
        with self.assertNumQueries(4):
            response = self.client.get("/api/v1/me/achievements/")
        body = response.json()
        self.assertEqual(body["count"], 2)
        types = {row["achievement_type"] for row in body["results"]}
        self.assertEqual(types, {"course_completed", "first_course"})
        first_badge = body["results"][0]["badge"]
        self.assertIn("title_th", first_badge)
        self.assertTrue(first_badge["icon"])


class BadgeCatalogApiTests(TestCase):
    """GET /api/v1/achievements/  what there is to earn."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/achievements/"

    def test_anonymous_can_read_the_catalog(self) -> None:
        # Badge definitions describe the platform, not any user, so the
        # catalogue carries nothing worth gating (ADR 0024).
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json())

    def test_catalog_lists_every_seeded_badge(self) -> None:
        response = self.client.get(self.url)

        slugs = {row["slug"] for row in response.json()}
        self.assertEqual(
            slugs,
            {
                "course_completed",
                "first_course",
                "ten_courses",
                "quiz_master",
                "recipe_author",
            },
        )

    def test_catalog_carries_display_metadata_only(self) -> None:
        response = self.client.get(self.url)

        row = response.json()[0]
        self.assertEqual(
            set(row),
            {
                "slug",
                "title_th",
                "title_en",
                "description_th",
                "description_en",
                "icon",
            },
        )

    def test_deactivated_badges_are_hidden_without_unearning_anything(self) -> None:
        student = create_user()
        course = build_completed_course(student=student, instructor=create_user())
        certificate_service.issue_if_completed(
            user_id=student.id, course_slug=course.slug
        )
        BadgeDefinition.objects.filter(slug="first_course").update(is_active=False)

        catalog = self.client.get(self.url).json()
        self.client.force_login(student)
        earned = self.client.get("/api/v1/me/achievements/").json()

        self.assertNotIn("first_course", {row["slug"] for row in catalog})
        self.assertIn(
            "first_course", {row["achievement_type"] for row in earned["results"]}
        )
