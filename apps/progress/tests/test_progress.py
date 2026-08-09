"""Lesson completion, course derivation and the activity ledger.

Ported from ``apps/lessons/tests/test_progress.py`` when the domain moved
(Phase 6) — every Phase 3 behaviour assertion is preserved, updated only for
the new field semantics (``completed_at`` nullable flag,
``first_completed_at`` history).
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.courses.constants import EnrollmentStatus
from apps.courses.models import Enrollment
from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.progress.constants import ActivityType
from apps.progress.exceptions import EnrollmentRequiredError
from apps.progress.models import CourseProgress, LearningActivity
from apps.progress.services import progress_service
from apps.progress.tests.factories import complete_lesson_row
from apps.users.tests.factories import create_user


class CompleteLessonTests(TestCase):
    """POST/DELETE complete semantics and course auto-completion."""

    def setUp(self) -> None:
        self.instructor = create_user()
        self.student = create_user()
        self.course = create_published_course(
            instructor=self.instructor, slug="baking-101"
        )
        self.lesson_a = create_lesson(course=self.course, title="A")
        self.lesson_b = create_lesson(course=self.course, title="B")
        enroll_user(user=self.student, course=self.course)

    def test_complete_marks_the_lesson(self) -> None:
        progress, course_completed = progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )

        self.assertTrue(progress.completed)
        self.assertIsNotNone(progress.completed_at)
        self.assertEqual(progress.first_completed_at, progress.completed_at)
        self.assertFalse(course_completed)

    def test_complete_is_idempotent(self) -> None:
        first, _ = progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        stamp = first.completed_at

        second, _ = progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )

        self.assertEqual(second.completed_at, stamp)

    def test_completion_requires_enrollment(self) -> None:
        outsider = create_user()

        with self.assertRaises(EnrollmentRequiredError):
            progress_service.complete_lesson(
                lesson_id=self.lesson_a.pk, user_id=outsider.id
            )

    def test_preview_lesson_still_requires_enrollment_to_complete(self) -> None:
        # Reading a preview is free; recording progress is a course activity.
        preview = create_lesson(course=self.course, is_preview=True)
        outsider = create_user()

        with self.assertRaises(EnrollmentRequiredError):
            progress_service.complete_lesson(
                lesson_id=preview.pk, user_id=outsider.id
            )

    def test_completing_every_lesson_completes_the_course(self) -> None:
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        _, course_completed = progress_service.complete_lesson(
            lesson_id=self.lesson_b.pk, user_id=self.student.id
        )

        self.assertTrue(course_completed)
        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertEqual(enrollment.status, EnrollmentStatus.COMPLETED)
        self.assertIsNotNone(enrollment.completed_at)
        # And this domain's own durable fact.
        row = CourseProgress.objects.get(user=self.student, course=self.course)
        self.assertIsNotNone(row.completed_at)

    def test_course_completion_is_stamped_once(self) -> None:
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        progress_service.complete_lesson(
            lesson_id=self.lesson_b.pk, user_id=self.student.id
        )
        stamp = CourseProgress.objects.get(
            user=self.student, course=self.course
        ).completed_at

        # Un-complete and re-complete — the stamp must not move.
        progress_service.uncomplete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )

        self.assertEqual(
            CourseProgress.objects.get(
                user=self.student, course=self.course
            ).completed_at,
            stamp,
        )

    def test_draft_lessons_do_not_block_course_completion(self) -> None:
        create_lesson(course=self.course, status="draft")

        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        _, course_completed = progress_service.complete_lesson(
            lesson_id=self.lesson_b.pk, user_id=self.student.id
        )

        self.assertTrue(course_completed)

    def test_uncomplete_clears_flag_but_keeps_history(self) -> None:
        completed, _ = progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        stamp = completed.first_completed_at

        cleared = progress_service.uncomplete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )

        self.assertFalse(cleared.completed)
        self.assertIsNone(cleared.completed_at)
        self.assertEqual(cleared.first_completed_at, stamp)

    def test_uncomplete_does_not_downgrade_a_completed_course(self) -> None:
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        progress_service.complete_lesson(
            lesson_id=self.lesson_b.pk, user_id=self.student.id
        )

        progress_service.uncomplete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )

        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertEqual(enrollment.status, EnrollmentStatus.COMPLETED)
        self.assertIsNotNone(
            CourseProgress.objects.get(
                user=self.student, course=self.course
            ).completed_at
        )

    def test_adding_a_lesson_never_downgrades_completion(self) -> None:
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        progress_service.complete_lesson(
            lesson_id=self.lesson_b.pk, user_id=self.student.id
        )

        create_lesson(course=self.course, title="Added later")

        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertEqual(enrollment.status, EnrollmentStatus.COMPLETED)

    def test_completion_records_a_daily_activity_fact(self) -> None:
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        progress_service.complete_lesson(
            lesson_id=self.lesson_b.pk, user_id=self.student.id
        )

        # Two completions on one day are one fact — the streak dedupe.
        facts = LearningActivity.objects.filter(
            user=self.student, activity_type=ActivityType.LESSON_COMPLETED
        )
        self.assertEqual(facts.count(), 1)

    def test_uncomplete_never_erases_activity(self) -> None:
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        progress_service.uncomplete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )

        self.assertEqual(
            LearningActivity.objects.filter(user=self.student).count(), 1
        )


class CourseProgressEndpointTests(TestCase):
    """GET /courses/{slug}/progress/ — now served by the progress app."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.instructor = create_user()
        self.student = create_user()
        self.course = create_published_course(
            instructor=self.instructor, slug="baking-101"
        )
        self.lesson_a = create_lesson(course=self.course, title="A")
        self.lesson_b = create_lesson(course=self.course, title="B")
        enroll_user(user=self.student, course=self.course)
        self.url = reverse("course_progress:detail", kwargs={"slug": "baking-101"})

    def test_progress_shape(self) -> None:
        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        self.client.force_login(self.student)

        body = self.client.get(self.url).json()

        self.assertEqual(body["total_lessons"], 2)
        self.assertEqual(body["completed_lessons"], 1)
        self.assertEqual(body["percent"], 50)
        self.assertEqual(len(body["lessons"]), 2)
        self.assertEqual(body["enrollment_status"], "active")
        self.assertIsNone(body["completed_at"])

    def test_progress_requires_authentication(self) -> None:
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_progress_requires_enrollment(self) -> None:
        outsider = create_user()
        self.client.force_login(outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "enrollment_required")

    def test_dropped_student_loses_progress_access_until_re_enrolling(self) -> None:
        # Same gate as lesson content: history is kept, not served, while dropped.
        from apps.courses.services import enrollment_service

        progress_service.complete_lesson(
            lesson_id=self.lesson_a.pk, user_id=self.student.id
        )
        enrollment_service.unenroll(user_id=self.student.id, slug="baking-101")
        self.client.force_login(self.student)

        dropped = self.client.get(self.url)
        self.assertEqual(dropped.status_code, 403)

        enrollment_service.enroll(user_id=self.student.id, slug="baking-101")
        restored = self.client.get(self.url)
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["completed_lessons"], 1)

    def test_progress_read_self_heals_a_missed_completion(self) -> None:
        # Simulate the concurrent-last-two-lessons race: rows say complete but
        # the write-through never fired.
        complete_lesson_row(user=self.student, lesson=self.lesson_a)
        complete_lesson_row(user=self.student, lesson=self.lesson_b)
        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)

        self.client.force_login(self.student)
        body = self.client.get(self.url).json()

        self.assertEqual(body["percent"], 100)
        self.assertEqual(body["enrollment_status"], "completed")
        self.assertIsNotNone(body["completed_at"])
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, EnrollmentStatus.COMPLETED)

    def test_complete_endpoint_round_trip(self) -> None:
        self.client.force_login(self.student)
        url = reverse("lesson_progress:complete", kwargs={"lesson_id": self.lesson_a.pk})

        completed = self.client.post(url)
        self.assertEqual(completed.status_code, 200)
        body = completed.json()
        self.assertTrue(body["completed"])
        self.assertFalse(body["course_completed"])
        self.assertEqual(body["lesson_id"], self.lesson_a.pk)

        cleared = self.client.delete(url)
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(cleared.json()["completed"])
        # History survives un-completing.
        self.assertIsNotNone(cleared.json()["first_completed_at"])

    def test_completing_the_last_lesson_reports_course_completed(self) -> None:
        self.client.force_login(self.student)
        self.client.post(
            reverse("lesson_progress:complete", kwargs={"lesson_id": self.lesson_a.pk})
        )
        final = self.client.post(
            reverse("lesson_progress:complete", kwargs={"lesson_id": self.lesson_b.pk})
        )
        self.assertTrue(final.json()["course_completed"])


class MyProgressTests(TestCase):
    """GET /me/progress/ — flat query count, correct aggregates."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.instructor = create_user()
        self.student = create_user()

    def _course_with_lessons(self, slug: str, lesson_count: int) -> object:
        course = create_published_course(instructor=self.instructor, slug=slug)
        lessons = [create_lesson(course=course) for _ in range(lesson_count)]
        enroll_user(user=self.student, course=course)
        return course, lessons

    def test_overview_aggregates_per_course(self) -> None:
        _course1, lessons1 = self._course_with_lessons("mp-bread", 2)
        _course2, lessons2 = self._course_with_lessons("mp-cake", 3)
        progress_service.complete_lesson(
            lesson_id=lessons1[0].pk, user_id=self.student.id
        )
        progress_service.complete_lesson(
            lesson_id=lessons1[1].pk, user_id=self.student.id
        )
        progress_service.complete_lesson(
            lesson_id=lessons2[0].pk, user_id=self.student.id
        )

        self.client.force_login(self.student)
        body = self.client.get("/api/v1/me/progress/").json()

        by_slug = {row["slug"]: row for row in body["courses"]}
        bread = by_slug["mp-bread"]
        self.assertEqual(bread["completed_lessons"], 2)
        self.assertEqual(bread["total_lessons"], 2)
        self.assertEqual(bread["percentage"], 100)
        self.assertIsNotNone(bread["completed_at"])
        cake = by_slug["mp-cake"]
        self.assertEqual(cake["completed_lessons"], 1)
        self.assertEqual(cake["percentage"], 33)
        self.assertIsNone(cake["completed_at"])

    def test_overview_query_count_is_flat(self) -> None:
        for index in range(3):
            _, lessons = self._course_with_lessons(f"mp-flat-{index}", 2)
            progress_service.complete_lesson(
                lesson_id=lessons[0].pk, user_id=self.student.id
            )

        self.client.force_login(self.student)
        with self.assertNumQueries(7):
            # session + user + enrolled ids + courses (+ categories prefetch)
            # + completed counts + completion map — flat in course count.
            response = self.client.get("/api/v1/me/progress/")
        self.assertEqual(len(response.json()["courses"]), 3)

    def test_overview_requires_authentication(self) -> None:
        self.assertEqual(self.client.get("/api/v1/me/progress/").status_code, 401)

    def test_overview_is_empty_without_enrollments(self) -> None:
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get("/api/v1/me/progress/").json(), {"courses": []}
        )
