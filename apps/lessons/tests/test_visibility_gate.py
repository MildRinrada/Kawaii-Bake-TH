"""The lesson gate matrix.

Asserts the exact 404 / 401 / 403-``enrollment_required`` / 200 split of the
two-layer rule:

* Layer 1 (404): course hidden, or lesson unpublished for a non-owner 
  existence protection, identical to Phase 2.
* Layer 2 (401/403): existence is public via the syllabus; the viewer simply
  may not read the content yet.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.courses.constants import CourseVisibility, EnrollmentStatus
from apps.courses.tests.factories import (
    create_course,
    create_published_course,
    enroll_user,
)
from apps.lessons.constants import LessonStatus
from apps.lessons.tests.factories import create_lesson
from apps.users.tests.factories import create_user


class LessonGateMatrixTests(TestCase):
    """Course state × lesson state × preview × viewer class."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.instructor = create_user(username="teacher")
        cls.enrolled = create_user(username="student")
        cls.dropped = create_user(username="dropout")
        cls.outsider = create_user(username="outsider")
        cls.staff = create_user(username="staffer", is_staff=True)

        cls.course = create_published_course(
            instructor=cls.instructor, slug="baking-101"
        )
        enroll_user(user=cls.enrolled, course=cls.course)
        enroll_user(
            user=cls.dropped, course=cls.course, status=EnrollmentStatus.DROPPED
        )

        cls.lesson = create_lesson(course=cls.course, title="Kneading")
        cls.preview = create_lesson(
            course=cls.course, title="Welcome", is_preview=True
        )
        cls.draft_lesson = create_lesson(
            course=cls.course, title="Unfinished", status=LessonStatus.DRAFT
        )

    def _get(self, lesson_id: int, user=None):
        client = APIClient()
        if user is not None:
            client.force_login(user)
        return client.get(reverse("lessons:detail", kwargs={"lesson_id": lesson_id}))

    # --- Layer 2: gating on a visible lesson --------------------------------

    def test_anonymous_gets_401_on_gated_content(self) -> None:
        response = self._get(self.lesson.pk)

        self.assertEqual(response.status_code, 401)

    def test_non_enrolled_gets_403_enrollment_required(self) -> None:
        # 403, not 404: the syllabus already made this lesson public, so a 404
        # would be a lie  and the frontend needs the code for the Enroll CTA.
        response = self._get(self.lesson.pk, user=self.outsider)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "enrollment_required")

    def test_dropped_student_gets_403(self) -> None:
        response = self._get(self.lesson.pk, user=self.dropped)

        self.assertEqual(response.status_code, 403)

    def test_enrolled_student_reads_content(self) -> None:
        response = self._get(self.lesson.pk, user=self.enrolled)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "Lesson body.")

    def test_instructor_reads_own_content_without_enrollment(self) -> None:
        response = self._get(self.lesson.pk, user=self.instructor)

        self.assertEqual(response.status_code, 200)

    def test_staff_reads_anything(self) -> None:
        response = self._get(self.draft_lesson.pk, user=self.staff)

        self.assertEqual(response.status_code, 200)

    # --- Preview lessons ----------------------------------------------------

    def test_preview_is_readable_by_anonymous(self) -> None:
        response = self._get(self.preview.pk)

        self.assertEqual(response.status_code, 200)

    def test_preview_is_readable_by_non_enrolled(self) -> None:
        response = self._get(self.preview.pk, user=self.outsider)

        self.assertEqual(response.status_code, 200)

    # --- Layer 1: existence protection --------------------------------------

    def test_draft_lesson_is_404_for_students(self) -> None:
        for viewer in (None, self.outsider, self.enrolled):
            with self.subTest(viewer=viewer):
                response = self._get(self.draft_lesson.pk, user=viewer)
                self.assertEqual(response.status_code, 404)

    def test_lesson_on_hidden_course_is_404_even_when_enrolled_gate_would_pass(
        self,
    ) -> None:
        private_course = create_published_course(
            instructor=self.instructor,
            slug="secret-course",
            visibility=CourseVisibility.PRIVATE,
        )
        hidden_lesson = create_lesson(course=private_course)

        for viewer in (None, self.outsider):
            with self.subTest(viewer=viewer):
                response = self._get(hidden_lesson.pk, user=viewer)
                self.assertEqual(response.status_code, 404)

    def test_lesson_on_draft_course_is_404(self) -> None:
        draft_course = create_course(instructor=self.instructor, slug="wip-course")
        lesson = create_lesson(course=draft_course)

        response = self._get(lesson.pk, user=self.outsider)

        self.assertEqual(response.status_code, 404)

    def test_unknown_lesson_is_404(self) -> None:
        response = self._get(999_999, user=self.enrolled)

        self.assertEqual(response.status_code, 404)

    def test_gate_failure_and_missing_lesson_have_different_codes_by_design(
        self,
    ) -> None:
        # The 403 deliberately differs from 404: existence is already public.
        gated = self._get(self.lesson.pk, user=self.outsider)
        missing = self._get(999_999, user=self.outsider)

        self.assertEqual(gated.json()["error"]["code"], "enrollment_required")
        self.assertEqual(missing.json()["error"]["code"], "not_found")

    # --- Syllabus -----------------------------------------------------------

    def test_syllabus_is_public_but_metadata_only(self) -> None:
        response = APIClient().get(
            reverse("course_lessons:list", kwargs={"slug": "baking-101"})
        )

        self.assertEqual(response.status_code, 200)
        titles = {item["title"] for item in response.json()}
        self.assertIn("Kneading", titles)
        self.assertNotIn("Unfinished", titles)  # drafts hidden from the syllabus
        for item in response.json():
            self.assertNotIn("content", item)
            self.assertNotIn("video_url", item)

    def test_syllabus_shows_drafts_to_the_instructor(self) -> None:
        client = APIClient()
        client.force_login(self.instructor)

        response = client.get(
            reverse("course_lessons:list", kwargs={"slug": "baking-101"})
        )

        titles = {item["title"] for item in response.json()}
        self.assertIn("Unfinished", titles)

    def test_syllabus_carries_no_learner_state(self) -> None:
        # Since Phase 6 the syllabus is pure lesson metadata  completion
        # lives at the progress app's endpoints (ADR 0012).
        from apps.progress.tests.factories import complete_lesson_row

        complete_lesson_row(user=self.enrolled, lesson=self.lesson)
        client = APIClient()
        client.force_login(self.enrolled)

        response = client.get(
            reverse("course_lessons:list", kwargs={"slug": "baking-101"})
        )

        for item in response.json():
            self.assertNotIn("completed", item)
            self.assertNotIn("progress_percent", item)

    def test_syllabus_of_hidden_course_is_404(self) -> None:
        create_published_course(
            instructor=self.instructor,
            slug="hidden-course",
            visibility=CourseVisibility.PRIVATE,
        )

        response = APIClient().get(
            reverse("course_lessons:list", kwargs={"slug": "hidden-course"})
        )

        self.assertEqual(response.status_code, 404)
