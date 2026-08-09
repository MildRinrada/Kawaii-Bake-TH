"""Tests for lesson CRUD, reordering, and the published-lesson counter."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.courses.models import Course
from apps.courses.tests.factories import create_published_course
from apps.lessons.exceptions import InvalidReorderError
from apps.lessons.models import Lesson
from apps.lessons.services import lesson_service
from apps.lessons.tests.factories import create_lesson
from apps.progress.models import LessonProgress
from apps.progress.tests.factories import complete_lesson_row
from apps.users.tests.factories import create_user


def counter(course: Course) -> int:
    """Read the counter fresh from the database."""
    return Course.objects.get(pk=course.pk).published_lesson_count


class LessonCounterTests(TestCase):
    """The counter must stay true across every mutation type."""

    def setUp(self) -> None:
        self.instructor = create_user()
        self.course = create_published_course(
            instructor=self.instructor, slug="baking-101"
        )

    def test_create_published_increments(self) -> None:
        create_lesson(course=self.course)

        self.assertEqual(counter(self.course), 1)

    def test_create_draft_does_not_increment(self) -> None:
        create_lesson(course=self.course, status="draft")

        self.assertEqual(counter(self.course), 0)

    def test_publish_transition_increments(self) -> None:
        lesson = create_lesson(course=self.course, status="draft")

        lesson_service.update_lesson(
            lesson_id=lesson.pk,
            viewer_id=self.instructor.id,
            data={"status": "published"},
        )

        self.assertEqual(counter(self.course), 1)

    def test_unpublish_transition_decrements(self) -> None:
        lesson = create_lesson(course=self.course)

        lesson_service.update_lesson(
            lesson_id=lesson.pk, viewer_id=self.instructor.id, data={"status": "draft"}
        )

        self.assertEqual(counter(self.course), 0)

    def test_delete_decrements(self) -> None:
        lesson = create_lesson(course=self.course)

        lesson_service.delete_lesson(
            lesson_id=lesson.pk, viewer_id=self.instructor.id
        )

        self.assertEqual(counter(self.course), 0)

    def test_non_status_update_leaves_counter_alone(self) -> None:
        lesson = create_lesson(course=self.course)

        lesson_service.update_lesson(
            lesson_id=lesson.pk, viewer_id=self.instructor.id, data={"title": "Renamed"}
        )

        self.assertEqual(counter(self.course), 1)

    def test_recount_command_repairs_drift(self) -> None:
        from django.core.management import call_command

        # Bypass the repository on purpose to create drift.
        create_lesson(course=self.course, via_repository=False)
        self.assertEqual(counter(self.course), 0)

        call_command("recount_lessons")

        self.assertEqual(counter(self.course), 1)


class LessonCrudTests(TestCase):
    """Individual lesson CRUD — never collection-replace."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.instructor = create_user()
        self.stranger = create_user()
        self.course = create_published_course(
            instructor=self.instructor, slug="baking-101"
        )
        self.list_url = reverse("course_lessons:list", kwargs={"slug": "baking-101"})

    def test_instructor_can_create_a_lesson(self) -> None:
        self.client.force_login(self.instructor)

        response = self.client.post(
            self.list_url, {"title": "Kneading dough"}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["position"], 0)

    def test_lessons_append_at_the_end(self) -> None:
        self.client.force_login(self.instructor)
        self.client.post(self.list_url, {"title": "First"}, format="json")

        second = self.client.post(self.list_url, {"title": "Second"}, format="json")

        self.assertEqual(second.json()["position"], 1)

    def test_stranger_cannot_create(self) -> None:
        self.client.force_login(self.stranger)

        response = self.client.post(self.list_url, {"title": "Mine"}, format="json")

        self.assertEqual(response.status_code, 404)

    def test_editing_a_lesson_does_not_touch_progress(self) -> None:
        # The reason lessons are never collection-replaced: progress must
        # survive edits.
        student = create_user()
        lesson = create_lesson(course=self.course)
        complete_lesson_row(user=student, lesson=lesson)

        lesson_service.update_lesson(
            lesson_id=lesson.pk,
            viewer_id=self.instructor.id,
            data={"title": "Renamed", "content": "New body."},
        )

        self.assertTrue(
            LessonProgress.objects.filter(user=student, lesson=lesson).exists()
        )

    def test_delete_renumbers_survivors(self) -> None:
        a = create_lesson(course=self.course, title="A")
        b = create_lesson(course=self.course, title="B")
        c = create_lesson(course=self.course, title="C")

        lesson_service.delete_lesson(lesson_id=b.pk, viewer_id=self.instructor.id)

        positions = dict(
            Lesson.objects.filter(course=self.course).values_list("title", "position")
        )
        self.assertEqual(positions, {"A": 0, "C": 1})
        self.assertEqual(a.pk, Lesson.objects.get(title="A").pk)
        self.assertEqual(c.pk, Lesson.objects.get(title="C").pk)

    def test_linking_an_invisible_recipe_is_rejected(self) -> None:
        from apps.recipes.tests.factories import create_recipe

        other = create_user()
        private_recipe = create_recipe(author=other, slug="their-draft")
        self.client.force_login(self.instructor)

        response = self.client.post(
            self.list_url,
            {"title": "Recipe lesson", "recipe_id": private_recipe.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_recipe")

    def test_linked_recipe_that_goes_private_degrades_to_null(self) -> None:
        from apps.courses.tests.factories import enroll_user
        from apps.recipes.constants import RecipeVisibility
        from apps.recipes.tests.factories import create_published_recipe

        recipe = create_published_recipe(author=self.instructor, slug="croissant")
        lesson = create_lesson(course=self.course, recipe=recipe)
        student = create_user()
        enroll_user(user=student, course=self.course)

        recipe.visibility = RecipeVisibility.PRIVATE
        recipe.save(update_fields=["visibility"])

        self.client.force_login(student)
        response = self.client.get(
            reverse("lessons:detail", kwargs={"lesson_id": lesson.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["recipe"])


class LessonReorderTests(TestCase):
    """The drag-and-drop reorder endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.instructor = create_user()
        self.course = create_published_course(
            instructor=self.instructor, slug="baking-101"
        )
        self.a = create_lesson(course=self.course, title="A")
        self.b = create_lesson(course=self.course, title="B")
        self.c = create_lesson(course=self.course, title="C")
        self.url = reverse("course_lessons:reorder", kwargs={"slug": "baking-101"})

    def test_reorder_applies_the_array_order(self) -> None:
        self.client.force_login(self.instructor)

        response = self.client.post(
            self.url,
            {"lesson_ids": [self.c.pk, self.a.pk, self.b.pk]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()]
        self.assertEqual(titles, ["C", "A", "B"])

    def test_reorder_reports_the_diff_on_a_bad_payload(self) -> None:
        foreign = create_lesson(
            course=create_published_course(instructor=self.instructor, slug="other")
        )
        self.client.force_login(self.instructor)

        response = self.client.post(
            self.url,
            {"lesson_ids": [self.a.pk, self.a.pk, foreign.pk]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        details = response.json()["error"]["details"]
        self.assertIn(self.a.pk, details["duplicate_ids"])
        self.assertIn(foreign.pk, details["unknown_ids"])
        self.assertIn(self.b.pk, details["missing_ids"])

    def test_reorder_survives_a_reversed_full_array(self) -> None:
        with self.assertRaises(InvalidReorderError):
            lesson_service.reorder_lessons(
                course_slug="baking-101",
                viewer_id=self.instructor.id,
                ordered_ids=[self.a.pk],
            )

    def test_stranger_cannot_reorder(self) -> None:
        stranger = create_user()
        self.client.force_login(stranger)

        response = self.client.post(
            self.url,
            {"lesson_ids": [self.a.pk, self.b.pk, self.c.pk]},
            format="json",
        )

        self.assertEqual(response.status_code, 404)


class CourseListPerformanceTests(TestCase):
    """The course list must not grow queries with results."""

    def test_query_count_is_constant(self) -> None:
        instructor = create_user()
        for index in range(15):
            course = create_published_course(
                instructor=instructor,
                slug=f"course-{index}",
                thumbnail="courses/thumbnails/x.jpg",
            )
            create_lesson(course=course)

        client = APIClient()
        # count + page rows + categories prefetch. lesson_count comes from the
        # counter column, so lessons add nothing.
        with self.assertNumQueries(3):
            response = client.get(reverse("courses:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["lesson_count"], 1)
