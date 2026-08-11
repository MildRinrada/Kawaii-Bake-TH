"""Service-layer tests: the issuance gates, immutability, achievements."""

from __future__ import annotations

from django.test import TestCase

from apps.certificates.constants import AchievementType
from apps.certificates.exceptions import (
    CertificateCourseNotFoundError,
    CertificateEnrollmentRequiredError,
    CertificateNotFoundError,
    CourseNotCompletedError,
)
from apps.certificates.models import Achievement
from apps.certificates.services import achievement_service, certificate_service
from apps.certificates.tests.factories import build_completed_course
from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.users.tests.factories import create_user


class IssuanceGateTests(TestCase):
    """404 → 403 → 409 in order, then idempotent success."""

    def setUp(self) -> None:
        self.student = create_user(username="issuer")
        self.instructor = create_user(username="issuerinst")

    def test_hidden_course_is_404(self) -> None:
        create_published_course(
            instructor=self.instructor, slug="issue-draft", status="draft"
        )
        with self.assertRaises(CertificateCourseNotFoundError):
            certificate_service.issue_if_completed(
                user_id=self.student.id, course_slug="issue-draft"
            )

    def test_not_enrolled_is_403(self) -> None:
        create_published_course(instructor=self.instructor, slug="issue-open")
        with self.assertRaises(CertificateEnrollmentRequiredError):
            certificate_service.issue_if_completed(
                user_id=self.student.id, course_slug="issue-open"
            )

    def test_incomplete_course_is_409(self) -> None:
        course = create_published_course(
            instructor=self.instructor, slug="issue-half"
        )
        create_lesson(course=course)
        enroll_user(user=self.student, course=course)
        with self.assertRaises(CourseNotCompletedError):
            certificate_service.issue_if_completed(
                user_id=self.student.id, course_slug="issue-half"
            )

    def test_completed_course_issues_with_snapshot(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        certificate, created = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

        self.assertTrue(created)
        self.assertRegex(certificate.certificate_number, r"^KB-\d{4}-\d{6}$")
        # No display name was ever set on this profile, so the snapshot
        # falls back to the handle.
        self.assertEqual(certificate.student_name, self.student.username)
        self.assertEqual(certificate.course_title, course.title)
        self.assertIsNotNone(certificate.completed_at)
        self.assertIsNotNone(certificate.issued_at)

    def test_the_snapshot_prefers_the_real_name_over_the_handle(self) -> None:
        self.student.profile.display_name = "สมชาย ใจดี"
        self.student.profile.save(update_fields=["display_name"])
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )

        certificate, _created = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

        self.assertEqual(certificate.student_name, "สมชาย ใจดี")

    def test_the_snapshot_prefers_the_legal_name_above_everything(self) -> None:
        # Registration collects the legal name for exactly this line: it
        # outranks even a display name the learner set themselves.
        self.student.first_name = "มินตรา"
        self.student.last_name = "อบอุ่น"
        self.student.save(update_fields=["first_name", "last_name"])
        self.student.profile.display_name = "MildBakes"
        self.student.profile.save(update_fields=["display_name"])
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )

        certificate, _created = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

        self.assertEqual(certificate.student_name, "มินตรา อบอุ่น")

    def test_duplicate_issue_returns_the_same_certificate(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        first, created_first = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )
        second, created_second = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            first.certificate_number, second.certificate_number
        )


class RevocationAndVerificationTests(TestCase):
    """The stamp-once revoke and the public token lookup."""

    def setUp(self) -> None:
        self.student = create_user(username="verifier")
        self.instructor = create_user(username="verifierinst")
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        self.certificate, _ = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

    def test_verify_returns_valid_certificate(self) -> None:
        found = certificate_service.verify_token(
            token=self.certificate.verification_token
        )
        self.assertEqual(found.pk, self.certificate.pk)
        self.assertFalse(found.is_revoked)

    def test_verify_returns_revoked_certificate(self) -> None:
        certificate_service.revoke(
            certificate_id=self.certificate.pk, user_id=self.student.id
        )
        found = certificate_service.verify_token(
            token=self.certificate.verification_token
        )
        self.assertTrue(found.is_revoked)

    def test_unknown_token_is_404(self) -> None:
        import uuid

        with self.assertRaises(CertificateNotFoundError):
            certificate_service.verify_token(token=uuid.uuid4())

    def test_revoke_someone_elses_certificate_is_404(self) -> None:
        stranger = create_user(username="verifierstranger")
        with self.assertRaises(CertificateNotFoundError):
            certificate_service.revoke(
                certificate_id=self.certificate.pk, user_id=stranger.id
            )

    def test_immutable_fields_survive_revocation(self) -> None:
        number = self.certificate.certificate_number
        issued = self.certificate.issued_at
        revoked = certificate_service.revoke(
            certificate_id=self.certificate.pk, user_id=self.student.id
        )
        self.assertEqual(revoked.certificate_number, number)
        self.assertEqual(revoked.issued_at, issued)


class AchievementServiceTests(TestCase):
    """Course-completion awards, thresholds and recalculation."""

    def setUp(self) -> None:
        self.student = create_user(username="achsvc")
        self.instructor = create_user(username="achsvcinst")

    def _complete_and_issue(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

    def test_first_issuance_awards_completed_and_first(self) -> None:
        self._complete_and_issue()
        types = set(
            Achievement.objects.filter(user=self.student).values_list(
                "achievement_type", flat=True
            )
        )
        self.assertEqual(
            types,
            {AchievementType.COURSE_COMPLETED, AchievementType.FIRST_COURSE},
        )

    def test_second_issuance_awards_nothing_new(self) -> None:
        self._complete_and_issue()
        self._complete_and_issue()
        self.assertEqual(
            Achievement.objects.filter(user=self.student).count(), 2
        )

    def test_tenth_course_awards_ten_courses(self) -> None:
        for _ in range(10):
            self._complete_and_issue()
        self.assertTrue(
            Achievement.objects.filter(
                user=self.student,
                achievement_type=AchievementType.TEN_COURSES,
            ).exists()
        )

    def test_recalculate_repairs_missing_awards(self) -> None:
        self._complete_and_issue()
        Achievement.objects.filter(user=self.student).delete()

        awarded = achievement_service.recalculate(user_id=self.student.id)

        self.assertEqual(len(awarded), 2)
        self.assertEqual(
            Achievement.objects.filter(user=self.student).count(), 2
        )
        # Idempotent: a second pass finds nothing to repair.
        self.assertEqual(
            achievement_service.recalculate(user_id=self.student.id), []
        )
