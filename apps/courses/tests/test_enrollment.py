"""Tests for enrollment semantics."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.courses.constants import CourseVisibility, EnrollmentStatus
from apps.courses.exceptions import (
    CourseNotEnrollableError,
    CourseNotVisibleError,
    NotEnrolledError,
    OwnCourseEnrollmentError,
)
from apps.courses.models import Enrollment
from apps.courses.services import enrollment_service
from apps.courses.tests.factories import (
    create_course,
    create_published_course,
    enroll_user,
)
from apps.lessons.tests.factories import create_lesson
from apps.progress.models import LessonProgress
from apps.progress.tests.factories import complete_lesson_row
from apps.users.tests.factories import create_user


class EnrollServiceTests(TestCase):
    """Enrollment is idempotent, soft on drop, and history-preserving."""

    def setUp(self) -> None:
        self.instructor = create_user(username="teacher")
        self.student = create_user(username="student")
        self.course = create_published_course(
            instructor=self.instructor, slug="baking-101"
        )

    def test_first_enrollment_creates_an_active_row(self) -> None:
        enrollment, created = enrollment_service.enroll(
            user_id=self.student.id, slug="baking-101"
        )

        self.assertTrue(created)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertIsNotNone(enrollment.enrolled_at)

    def test_re_enroll_is_a_no_op(self) -> None:
        enrollment_service.enroll(user_id=self.student.id, slug="baking-101")

        _, created = enrollment_service.enroll(
            user_id=self.student.id, slug="baking-101"
        )

        self.assertFalse(created)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_unenroll_is_soft(self) -> None:
        enrollment_service.enroll(user_id=self.student.id, slug="baking-101")

        enrollment_service.unenroll(user_id=self.student.id, slug="baking-101")

        row = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertEqual(row.status, EnrollmentStatus.DROPPED)

    def test_unenroll_keeps_lesson_progress(self) -> None:
        lesson = create_lesson(course=self.course)
        enrollment_service.enroll(user_id=self.student.id, slug="baking-101")
        complete_lesson_row(user=self.student, lesson=lesson)

        enrollment_service.unenroll(user_id=self.student.id, slug="baking-101")

        self.assertTrue(
            LessonProgress.objects.filter(user=self.student, lesson=lesson).exists()
        )

    def test_re_enroll_after_drop_reactivates_the_same_row(self) -> None:
        enrollment_service.enroll(user_id=self.student.id, slug="baking-101")
        enrollment_service.unenroll(user_id=self.student.id, slug="baking-101")

        enrollment, created = enrollment_service.enroll(
            user_id=self.student.id, slug="baking-101"
        )

        self.assertFalse(created)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_re_enroll_after_completion_restores_completed(self) -> None:
        enrollment, _ = enrollment_service.enroll(
            user_id=self.student.id, slug="baking-101"
        )
        enrollment_service.record_course_completion(
            user_id=self.student.id, course_id=self.course.pk
        )
        enrollment_service.unenroll(user_id=self.student.id, slug="baking-101")

        restored, _ = enrollment_service.enroll(
            user_id=self.student.id, slug="baking-101"
        )

        self.assertEqual(restored.status, EnrollmentStatus.COMPLETED)
        self.assertIsNotNone(restored.completed_at)

    def test_instructor_cannot_enroll_in_own_course(self) -> None:
        with self.assertRaises(OwnCourseEnrollmentError):
            enrollment_service.enroll(user_id=self.instructor.id, slug="baking-101")

    def test_cannot_enroll_in_a_draft(self) -> None:
        create_course(instructor=self.instructor, slug="wip")

        # Draft is invisible to strangers, so this is a 404 — not a 400 that
        # would confirm the course exists.
        with self.assertRaises(CourseNotVisibleError):
            enrollment_service.enroll(user_id=self.student.id, slug="wip")

    def test_cannot_enroll_in_an_archived_course(self) -> None:
        course = create_published_course(instructor=self.instructor, slug="old")
        course.status = "archived"
        course.save(update_fields=["status"])
        # Archived + public is invisible to a non-enrolled stranger → 404 path;
        # for an already-enrolled student, enroll is a no-op — so use unlisted
        # visibility with an existing enrollment to reach the enrollable check.
        enrolled = create_user()
        enroll_user(user=enrolled, course=course)

        with self.assertRaises(CourseNotEnrollableError):
            enrollment_service.enroll(user_id=enrolled.id, slug="old")

    def test_unenroll_when_never_enrolled_is_404(self) -> None:
        with self.assertRaises(NotEnrolledError):
            enrollment_service.unenroll(user_id=self.student.id, slug="baking-101")

    def test_completion_never_downgrades(self) -> None:
        enrollment_service.enroll(user_id=self.student.id, slug="baking-101")
        enrollment_service.record_course_completion(
            user_id=self.student.id, course_id=self.course.pk
        )
        row = Enrollment.objects.get(user=self.student, course=self.course)
        stamp = row.completed_at

        # Recording again must not move the stamp.
        enrollment_service.record_course_completion(
            user_id=self.student.id, course_id=self.course.pk
        )

        row.refresh_from_db()
        self.assertEqual(row.completed_at, stamp)


class EnrollApiTests(TestCase):
    """The enroll/unenroll endpoints."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.instructor = create_user()
        self.student = create_user()
        self.course = create_published_course(
            instructor=self.instructor, slug="baking-101"
        )

    def test_enroll_returns_201_then_200(self) -> None:
        self.client.force_login(self.student)
        url = reverse("courses:enroll", kwargs={"slug": "baking-101"})

        first = self.client.post(url)
        second = self.client.post(url)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)

    def test_enroll_requires_authentication(self) -> None:
        response = self.client.post(
            reverse("courses:enroll", kwargs={"slug": "baking-101"})
        )

        self.assertEqual(response.status_code, 401)

    def test_enroll_in_hidden_course_is_404(self) -> None:
        create_published_course(
            instructor=self.instructor,
            slug="secret",
            visibility=CourseVisibility.PRIVATE,
        )
        self.client.force_login(self.student)

        response = self.client.post(reverse("courses:enroll", kwargs={"slug": "secret"}))

        self.assertEqual(response.status_code, 404)

    def test_unenroll_returns_204(self) -> None:
        self.client.force_login(self.student)
        self.client.post(reverse("courses:enroll", kwargs={"slug": "baking-101"}))

        response = self.client.delete(
            reverse("courses:unenroll", kwargs={"slug": "baking-101"})
        )

        self.assertEqual(response.status_code, 204)

    def test_course_detail_reports_enrollment_state(self) -> None:
        self.client.force_login(self.student)
        url = reverse("courses:detail", kwargs={"slug": "baking-101"})

        before = self.client.get(url).json()
        self.client.post(reverse("courses:enroll", kwargs={"slug": "baking-101"}))
        after = self.client.get(url).json()

        self.assertFalse(before["is_enrolled"])
        self.assertTrue(after["is_enrolled"])
