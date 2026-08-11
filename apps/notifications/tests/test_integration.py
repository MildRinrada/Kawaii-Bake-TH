"""Producer-wiring tests  the three events through the real services."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.certificates.services import certificate_service
from apps.certificates.tests.factories import build_completed_course
from apps.courses.services import enrollment_service
from apps.courses.tests.factories import create_published_course
from apps.notifications.constants import NotificationEventType
from apps.notifications.models import Notification, NotificationPreference
from apps.recipes.tests.factories import create_published_recipe
from apps.reviews.exceptions import OwnContentReviewError
from apps.reviews.services import review_service
from apps.users.tests.factories import create_user


class ReviewWiringTests(TestCase):
    """A review notifies the content owner  and only the owner."""

    def setUp(self) -> None:
        self.author = create_user(username="wireauthor")
        self.reviewer = create_user(username="wirereviewer")
        self.recipe = create_published_recipe(author=self.author, slug="wire-cake")

    def _review(self) -> None:
        review_service.create_review(
            user_id=self.reviewer.id,
            kind="recipe",
            slug=self.recipe.slug,
            data={"rating": 5, "comment": "อร่อยมาก"},
        )

    def test_owner_receives_exactly_one_notification(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self._review()

        rows = Notification.objects.filter(recipient=self.author)
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.event_type, "review_received")
        self.assertEqual(row.actor_handle, "wirereviewer")
        self.assertIn(self.recipe.title, row.body)
        self.assertIn("5 ดาว", row.body)
        self.assertEqual(row.link, f"/recipes/{self.recipe.slug}/reviews/")
        # The reviewer got nothing.
        self.assertFalse(
            Notification.objects.filter(recipient=self.reviewer).exists()
        )

    def test_self_review_still_blocked_and_silent(self) -> None:
        own = create_published_recipe(author=self.reviewer, slug="wire-own")
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(OwnContentReviewError):
                review_service.create_review(
                    user_id=self.reviewer.id,
                    kind="recipe",
                    slug=own.slug,
                    data={"rating": 5},
                )
        self.assertEqual(Notification.objects.count(), 0)

    def test_notification_failure_does_not_fail_the_review(self) -> None:
        with mock.patch.object(
            Notification.objects, "create", side_effect=RuntimeError("boom")
        ):
            with self.captureOnCommitCallbacks(execute=True):
                self._review()  # must not raise

        from apps.reviews.models import Review

        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 0)


class EnrollmentWiringTests(TestCase):
    """New and returning students are news; idempotent no-ops are not."""

    def setUp(self) -> None:
        self.instructor = create_user(username="wireinst")
        self.student = create_user(username="wirestudent")
        self.course = create_published_course(
            instructor=self.instructor, slug="wire-course"
        )

    def _enroll(self) -> None:
        enrollment_service.enroll(user_id=self.student.id, slug=self.course.slug)

    def test_new_enrollment_notifies_the_instructor(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self._enroll()

        row = Notification.objects.get(recipient=self.instructor)
        self.assertEqual(row.event_type, "course_enrollment")
        self.assertEqual(row.actor_handle, "wirestudent")
        self.assertIn(self.course.title, row.body)

    def test_duplicate_enrollment_stays_silent(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self._enroll()
            self._enroll()
        self.assertEqual(
            Notification.objects.filter(recipient=self.instructor).count(), 1
        )

    def test_reactivation_notifies_again(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self._enroll()
            enrollment_service.unenroll(
                user_id=self.student.id, slug=self.course.slug
            )
            self._enroll()
        self.assertEqual(
            Notification.objects.filter(recipient=self.instructor).count(), 2
        )


class AchievementWiringTests(TestCase):
    """First award notifies; idempotent repeats do not."""

    def setUp(self) -> None:
        self.student = create_user(username="wireach")
        self.instructor = create_user(username="wireachinst")

    def test_first_award_notifies_with_thai_badge_title(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        with self.captureOnCommitCallbacks(execute=True):
            certificate_service.issue_if_completed(
                user_id=self.student.id, course_slug=course.slug
            )

        rows = Notification.objects.filter(
            recipient=self.student,
            event_type=NotificationEventType.ACHIEVEMENT_EARNED,
        )
        # course_completed + first_course, each earned once.
        self.assertEqual(rows.count(), 2)
        self.assertTrue(all("ปลดล็อก" in row.body for row in rows))

    def test_repeat_award_stays_silent(self) -> None:
        for _ in range(2):
            course = build_completed_course(
                student=self.student, instructor=self.instructor
            )
            with self.captureOnCommitCallbacks(execute=True):
                certificate_service.issue_if_completed(
                    user_id=self.student.id, course_slug=course.slug
                )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student,
                event_type=NotificationEventType.ACHIEVEMENT_EARNED,
            ).count(),
            2,
        )

    def test_disabled_preference_silences_the_wire(self) -> None:
        NotificationPreference.objects.create(
            user=self.student,
            event_type=NotificationEventType.ACHIEVEMENT_EARNED,
            enabled=False,
        )
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        with self.captureOnCommitCallbacks(execute=True):
            certificate_service.issue_if_completed(
                user_id=self.student.id, course_slug=course.slug
            )
        self.assertEqual(
            Notification.objects.filter(recipient=self.student).count(), 0
        )
