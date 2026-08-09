"""The published-duration counter pushed to courses (ADR 0021)."""

from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import Course
from apps.courses.tests.factories import create_course
from apps.lessons.constants import LessonStatus
from apps.lessons.repositories import lesson_repository
from apps.lessons.tests.factories import create_lesson
from apps.users.tests.factories import create_user


class DurationCounterTests(TestCase):
    """Every lesson mutation keeps Course.published_duration_minutes true."""

    def setUp(self) -> None:
        instructor = create_user(email="t@example.com", username="teacher")
        self.course = create_course(instructor=instructor)

    def _duration(self) -> int:
        return Course.objects.get(pk=self.course.pk).published_duration_minutes

    def test_creating_published_lessons_sums_their_durations(self) -> None:
        create_lesson(course=self.course, duration_minutes=30)
        create_lesson(course=self.course, duration_minutes=45)

        self.assertEqual(self._duration(), 75)

    def test_draft_lessons_do_not_count(self) -> None:
        create_lesson(course=self.course, duration_minutes=30)
        create_lesson(
            course=self.course, duration_minutes=99, status=LessonStatus.DRAFT
        )

        self.assertEqual(self._duration(), 30)

    def test_zero_durations_do_not_break_the_sum(self) -> None:
        create_lesson(course=self.course, duration_minutes=0)
        create_lesson(course=self.course, duration_minutes=20)

        self.assertEqual(self._duration(), 20)

    def test_deleting_a_lesson_subtracts_its_duration(self) -> None:
        lesson = create_lesson(course=self.course, duration_minutes=30)
        create_lesson(course=self.course, duration_minutes=45)

        lesson_repository.delete_lesson(lesson=lesson)

        self.assertEqual(self._duration(), 45)

    def test_recount_command_repairs_drift(self) -> None:
        create_lesson(course=self.course, duration_minutes=25, via_repository=False)
        self.assertEqual(self._duration(), 0)  # drift: bypassed the choke point

        call_command("recount_lessons")

        self.assertEqual(self._duration(), 25)
