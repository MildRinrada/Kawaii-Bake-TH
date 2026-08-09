"""Phase 4 integration: the optional per-lesson quiz reference."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.exceptions import InvalidLessonQuizError
from apps.lessons.services import lesson_service
from apps.lessons.tests.factories import create_lesson
from apps.quizzes.constants import QuizStatus, QuizVisibility
from apps.quizzes.tests.factories import create_published_quiz, create_quiz
from apps.users.tests.factories import create_user


class LessonQuizLinkTests(TestCase):
    """A lesson holds a reference; quiz logic never crosses into lessons."""

    def setUp(self) -> None:
        self.instructor = create_user(username="lqinstructor")
        self.student = create_user(username="lqstudent")
        self.course = create_published_course(
            instructor=self.instructor, slug="quiz-course"
        )
        enroll_user(user=self.student, course=self.course)

    def test_linking_a_visible_quiz_succeeds(self) -> None:
        quiz = create_published_quiz(
            owner=self.instructor, visibility=QuizVisibility.UNLISTED
        )
        lesson = lesson_service.create_lesson(
            course_slug=self.course.slug,
            viewer_id=self.instructor.id,
            data={"title": "Lesson with quiz", "quiz_id": quiz.pk},
        )
        self.assertEqual(lesson.quiz_id, quiz.pk)

    def test_own_draft_quiz_is_linkable(self) -> None:
        quiz = create_quiz(owner=self.instructor, status=QuizStatus.DRAFT)
        lesson = lesson_service.create_lesson(
            course_slug=self.course.slug,
            viewer_id=self.instructor.id,
            data={"title": "Draft quiz link", "quiz_id": quiz.pk},
        )
        self.assertEqual(lesson.quiz_id, quiz.pk)

    def test_invisible_quiz_is_rejected(self) -> None:
        other = create_user(username="lqother")
        hidden = create_quiz(owner=other, status=QuizStatus.DRAFT)
        with self.assertRaises(InvalidLessonQuizError):
            lesson_service.create_lesson(
                course_slug=self.course.slug,
                viewer_id=self.instructor.id,
                data={"title": "Bad link", "quiz_id": hidden.pk},
            )

    def test_lesson_detail_embeds_quiz_ref_without_questions(self) -> None:
        quiz = create_published_quiz(owner=self.instructor)
        lesson = create_lesson(course=self.course, quiz=quiz)
        client = APIClient()
        client.force_login(self.student)

        response = client.get(reverse("lessons:detail", args=[lesson.pk]))

        self.assertEqual(response.status_code, 200)
        embed = response.json()["quiz"]
        self.assertEqual(embed["slug"], quiz.slug)
        self.assertNotIn("questions", embed)

    def test_hidden_quiz_degrades_to_null_in_the_embed(self) -> None:
        quiz = create_published_quiz(owner=self.instructor)
        lesson = create_lesson(course=self.course, quiz=quiz)
        quiz.status = QuizStatus.DRAFT
        quiz.save(update_fields=["status"])
        client = APIClient()
        client.force_login(self.student)

        response = client.get(reverse("lessons:detail", args=[lesson.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["quiz"])

    def test_deleting_a_quiz_nulls_the_link(self) -> None:
        quiz = create_quiz(owner=self.instructor)
        lesson = create_lesson(course=self.course, quiz=quiz)
        quiz.delete()
        lesson.refresh_from_db()
        self.assertIsNone(lesson.quiz_id)
