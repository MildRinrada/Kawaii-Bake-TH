"""Tests for course services: create, update, publish lifecycle."""

from __future__ import annotations

from django.test import TestCase

from apps.courses.constants import CourseStatus
from apps.courses.exceptions import (
    CourseNotPublishableError,
    CourseNotVisibleError,
    CourseSlugImmutableError,
    InvalidCourseCategoryError,
)
from apps.courses.services import course_service, publish_service
from apps.courses.tests.factories import THAI_COURSE_TITLE, create_course
from apps.lessons.tests.factories import create_lesson
from apps.recipes.tests.factories import create_category
from apps.users.tests.factories import create_user


class CourseCreateServiceTests(TestCase):
    """Creating courses."""

    def setUp(self) -> None:
        self.user = create_user()
        create_category(slug="bread")

    def _payload(self, **overrides) -> dict:
        payload = {
            "title": "Bread Fundamentals",
            "summary": "From flour to loaf.",
            "description": "A thorough, hands-on introduction to bread baking.",
            "category_slugs": ["bread"],
        }
        payload.update(overrides)
        return payload

    def test_create_makes_a_draft_with_slug(self) -> None:
        course = course_service.create_course(
            instructor_id=self.user.id, data=self._payload()
        )

        self.assertEqual(course.status, CourseStatus.DRAFT)
        self.assertEqual(course.slug, "bread-fundamentals")
        self.assertEqual(course.categories.count(), 1)
        self.assertEqual(course.published_lesson_count, 0)

    def test_thai_title_produces_a_thai_slug(self) -> None:
        course = course_service.create_course(
            instructor_id=self.user.id, data=self._payload(title=THAI_COURSE_TITLE)
        )

        self.assertNotEqual(course.slug, "")
        self.assertFalse(course.slug.startswith("course-"))
        self.assertTrue(any("฀" <= char <= "๿" for char in course.slug))

    def test_duplicate_title_gets_a_distinct_slug(self) -> None:
        first = course_service.create_course(
            instructor_id=self.user.id, data=self._payload()
        )
        second = course_service.create_course(
            instructor_id=self.user.id, data=self._payload()
        )

        self.assertNotEqual(first.slug, second.slug)

    def test_unknown_category_is_rejected(self) -> None:
        with self.assertRaises(InvalidCourseCategoryError):
            course_service.create_course(
                instructor_id=self.user.id, data=self._payload(category_slugs=["nope"])
            )

    def test_instructor_reverse_accessor_is_courses_taught(self) -> None:
        course = course_service.create_course(
            instructor_id=self.user.id, data=self._payload()
        )

        self.assertIn(course.pk, [c.pk for c in self.user.courses_taught.all()])


class CourseUpdateServiceTests(TestCase):
    """Updating courses."""

    def setUp(self) -> None:
        self.user = create_user()
        self.other = create_user()
        self.course = create_course(instructor=self.user, slug="bread-101")

    def test_partial_update(self) -> None:
        updated = course_service.update_course(
            slug="bread-101", viewer_id=self.user.id, data={"summary": "New summary."}
        )

        self.assertEqual(updated.summary, "New summary.")

    def test_stranger_update_is_404(self) -> None:
        with self.assertRaises(CourseNotVisibleError):
            course_service.update_course(
                slug="bread-101", viewer_id=self.other.id, data={"title": "Hijacked"}
            )

    def test_status_cannot_be_set_through_update(self) -> None:
        updated = course_service.update_course(
            slug="bread-101",
            viewer_id=self.user.id,
            data={"status": "published", "summary": "ok"},
        )

        self.assertEqual(updated.status, CourseStatus.DRAFT)

    def test_slug_frozen_after_publication(self) -> None:
        from django.utils import timezone

        self.course.published_at = timezone.now()
        self.course.save(update_fields=["published_at"])

        with self.assertRaises(CourseSlugImmutableError):
            course_service.update_course(
                slug="bread-101", viewer_id=self.user.id, data={"slug": "new-slug"}
            )


class CoursePublishServiceTests(TestCase):
    """The publish gate and lifecycle."""

    def setUp(self) -> None:
        self.user = create_user()
        self.course = create_course(
            instructor=self.user,
            slug="bread-101",
            thumbnail="courses/thumbnails/x.jpg",
        )

    def test_publish_without_lessons_reports_the_checklist(self) -> None:
        with self.assertRaises(CourseNotPublishableError) as ctx:
            publish_service.publish(slug="bread-101", viewer_id=self.user.id)

        self.assertIn("lessons", ctx.exception.details)

    def test_publish_gate_reads_the_counter_not_lesson_rows(self) -> None:
        # A draft lesson must not satisfy the gate: the counter counts
        # published lessons only.
        create_lesson(course=self.course, status="draft")

        with self.assertRaises(CourseNotPublishableError):
            publish_service.publish(slug="bread-101", viewer_id=self.user.id)

    def test_publish_succeeds_with_a_published_lesson(self) -> None:
        create_lesson(course=self.course)

        published = publish_service.publish(slug="bread-101", viewer_id=self.user.id)

        self.assertEqual(published.status, CourseStatus.PUBLISHED)
        self.assertIsNotNone(published.published_at)

    def test_publish_is_idempotent(self) -> None:
        create_lesson(course=self.course)
        first = publish_service.publish(slug="bread-101", viewer_id=self.user.id)
        stamp = first.published_at

        second = publish_service.publish(slug="bread-101", viewer_id=self.user.id)

        self.assertEqual(second.published_at, stamp)

    def test_missing_description_blocks_publish(self) -> None:
        self.course.description = ""
        self.course.save(update_fields=["description"])
        create_lesson(course=self.course)

        with self.assertRaises(CourseNotPublishableError) as ctx:
            publish_service.publish(slug="bread-101", viewer_id=self.user.id)

        self.assertIn("description", ctx.exception.details)

    def test_unpublish_keeps_published_at(self) -> None:
        create_lesson(course=self.course)
        publish_service.publish(slug="bread-101", viewer_id=self.user.id)
        self.course.refresh_from_db()
        stamp = self.course.published_at

        publish_service.unpublish(slug="bread-101", viewer_id=self.user.id)

        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.DRAFT)
        self.assertEqual(self.course.published_at, stamp)

    def test_archive_and_restore(self) -> None:
        create_lesson(course=self.course)
        publish_service.publish(slug="bread-101", viewer_id=self.user.id)

        publish_service.archive(slug="bread-101", viewer_id=self.user.id)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.ARCHIVED)

        publish_service.publish(slug="bread-101", viewer_id=self.user.id)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.PUBLISHED)
