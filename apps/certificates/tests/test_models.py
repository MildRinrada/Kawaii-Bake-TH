"""Model-layer tests: numbering, the active-partial-unique, seeded badges."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.certificates.constants import AchievementType
from apps.certificates.models import BadgeDefinition, Certificate
from apps.certificates.repositories import certificate_repository
from apps.courses.tests.factories import create_published_course
from apps.users.tests.factories import create_user


class CertificateNumberTests(TestCase):
    """Allocation format and monotonic sequence."""

    def setUp(self) -> None:
        self.user = create_user(username="certnum")
        self.instructor = create_user(username="certnuminst")

    def _issue(self, course):
        return certificate_repository.issue_certificate(
            user_id=self.user.id,
            course_id=course.id,
            student_name=self.user.username,
            course_title=course.title,
            completed_at=timezone.now(),
        )

    def test_numbers_are_year_prefixed_and_sequential(self) -> None:
        first = self._issue(
            create_published_course(instructor=self.instructor, slug="num-a")
        )
        second = self._issue(
            create_published_course(instructor=self.instructor, slug="num-b")
        )

        year = timezone.now().year
        self.assertEqual(first.certificate_number, f"KB-{year}-000001")
        self.assertEqual(second.certificate_number, f"KB-{year}-000002")

    def test_one_active_certificate_per_user_course(self) -> None:
        course = create_published_course(instructor=self.instructor, slug="num-c")
        self._issue(course)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._issue(course)

    def test_revocation_frees_the_slot_and_keeps_the_row(self) -> None:
        course = create_published_course(instructor=self.instructor, slug="num-d")
        original = self._issue(course)
        certificate_repository.revoke(certificate=original)

        reissued = self._issue(course)

        self.assertEqual(Certificate.objects.count(), 2)
        self.assertNotEqual(
            original.certificate_number, reissued.certificate_number
        )
        original.refresh_from_db()
        self.assertIsNotNone(original.revoked_at)

    def test_revoke_is_stamp_once(self) -> None:
        course = create_published_course(instructor=self.instructor, slug="num-e")
        certificate = self._issue(course)

        self.assertTrue(certificate_repository.revoke(certificate=certificate))
        certificate.refresh_from_db()
        first_stamp = certificate.revoked_at

        self.assertFalse(certificate_repository.revoke(certificate=certificate))
        certificate.refresh_from_db()
        self.assertEqual(certificate.revoked_at, first_stamp)


class AchievementModelTests(TestCase):
    """Uniqueness and the seeded badge set."""

    def setUp(self) -> None:
        self.user = create_user(username="achmodel")

    def test_award_is_idempotent(self) -> None:
        first, created_first = certificate_repository.award_achievement(
            user_id=self.user.id,
            achievement_type=AchievementType.FIRST_COURSE,
            metadata={"course_id": 1},
        )
        second, created_second = certificate_repository.award_achievement(
            user_id=self.user.id,
            achievement_type=AchievementType.FIRST_COURSE,
            metadata={"course_id": 999},
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        # Append-only: the original earning context is never rewritten.
        self.assertEqual(second.metadata, {"course_id": 1})

    def test_award_links_the_matching_badge(self) -> None:
        achievement, _ = certificate_repository.award_achievement(
            user_id=self.user.id,
            achievement_type=AchievementType.COURSE_COMPLETED,
        )
        self.assertEqual(achievement.badge.slug, "course_completed")
        self.assertEqual(achievement.badge.title_th, "จบคอร์สแรกสำเร็จ")

    def test_migration_seeded_a_badge_per_type(self) -> None:
        slugs = set(BadgeDefinition.objects.values_list("slug", flat=True))
        self.assertEqual(slugs, set(AchievementType.values))
