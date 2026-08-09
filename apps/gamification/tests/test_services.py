"""Service-layer tests: the curve, derivation, reconciliation, streaks."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.certificates.services import certificate_service
from apps.certificates.tests.factories import build_completed_course
from apps.gamification.constants import XPReason
from apps.gamification.models import UserLevel, XPTransaction
from apps.gamification.services import (
    level_service,
    streak_service,
    xp_service,
)
from apps.gamification.tests.factories import add_activity_day
from apps.recipes.tests.factories import create_published_recipe
from apps.reviews.tests.factories import create_review
from apps.users.tests.factories import create_user


class LevelCurveTests(TestCase):
    """The pure level function."""

    def test_empty_ledger_is_level_one(self) -> None:
        info = level_service.calculate_level(total_xp=0)
        self.assertEqual(info.level, 1)
        self.assertEqual(info.xp_into_level, 0)
        self.assertEqual(info.xp_for_next_level, 100)

    def test_progressive_thresholds(self) -> None:
        # Level 2 at 100 total; level 3 at 100+200=300 total.
        self.assertEqual(level_service.calculate_level(total_xp=99).level, 1)
        self.assertEqual(level_service.calculate_level(total_xp=100).level, 2)
        self.assertEqual(level_service.calculate_level(total_xp=299).level, 2)
        info = level_service.calculate_level(total_xp=300)
        self.assertEqual(info.level, 3)
        self.assertEqual(info.xp_into_level, 0)
        self.assertEqual(info.xp_for_next_level, 300)


class AwardTests(TestCase):
    """Appending to the ledger promotes the derived level."""

    def setUp(self) -> None:
        self.user = create_user(username="awarduser")

    def test_award_appends_and_refreshes_level(self) -> None:
        entry = xp_service.award(
            user_id=self.user.id,
            reason=XPReason.COURSE_COMPLETED,
            metadata={"course_id": 1},
        )
        self.assertEqual(entry.points, 100)

        level = UserLevel.objects.get(user=self.user)
        self.assertEqual(level.total_xp, 100)
        self.assertEqual(level.current_level, 2)

    def test_level_promotion_across_awards(self) -> None:
        # 3 × 100 = 300 total → exactly level 3.
        for _ in range(3):
            course_meta = {"source": "test"}
            xp_service.award(
                user_id=self.user.id,
                reason=XPReason.COURSE_COMPLETED,
                metadata=course_meta,
            )
        level = UserLevel.objects.get(user=self.user)
        self.assertEqual(level.total_xp, 300)
        self.assertEqual(level.current_level, 3)
        self.assertEqual(level.current_xp, 0)


class RecalculateTests(TestCase):
    """Reconciliation against real domain facts, idempotently."""

    def setUp(self) -> None:
        self.student = create_user(username="recalcuser")
        self.instructor = create_user(username="recalcinst")

    def test_rebuild_from_real_facts(self) -> None:
        # 1 completed lesson + 1 completed course (via the real progress
        # path), 1 certificate, 1 active review.
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )
        recipe = create_published_recipe(author=self.instructor, slug="xp-cake")
        create_review(user=self.student, recipe=recipe)

        appended = xp_service.recalculate(user_id=self.student.id)

        self.assertEqual(
            appended,
            {
                XPReason.LESSON_COMPLETED: 1,
                XPReason.COURSE_COMPLETED: 1,
                XPReason.CERTIFICATE_ISSUED: 1,
                XPReason.REVIEW_WRITTEN: 1,
            },
        )
        level = UserLevel.objects.get(user=self.student)
        self.assertEqual(level.total_xp, 10 + 100 + 25 + 5)

    def test_duplicate_recalc_appends_nothing(self) -> None:
        course = build_completed_course(
            student=self.student, instructor=self.instructor
        )
        certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )

        xp_service.recalculate(user_id=self.student.id)
        first_count = XPTransaction.objects.filter(user=self.student).count()

        second = xp_service.recalculate(user_id=self.student.id)

        self.assertEqual(second, {})
        self.assertEqual(
            XPTransaction.objects.filter(user=self.student).count(), first_count
        )

    def test_recalc_tops_up_after_new_facts(self) -> None:
        build_completed_course(student=self.student, instructor=self.instructor)
        xp_service.recalculate(user_id=self.student.id)

        build_completed_course(student=self.student, instructor=self.instructor)
        appended = xp_service.recalculate(user_id=self.student.id)

        self.assertEqual(appended[XPReason.LESSON_COMPLETED], 1)
        self.assertEqual(appended[XPReason.COURSE_COMPLETED], 1)

    def test_award_then_recalc_does_not_double_count(self) -> None:
        build_completed_course(student=self.student, instructor=self.instructor)
        # Manually awarded first (e.g. by a future push source)…
        xp_service.award(
            user_id=self.student.id, reason=XPReason.LESSON_COMPLETED
        )
        # …reconciliation sees the ledger already covers the fact.
        appended = xp_service.recalculate(user_id=self.student.id)
        self.assertNotIn(XPReason.LESSON_COMPLETED, appended)


class StreakTests(TestCase):
    """Derivation from planted day-facts."""

    def setUp(self) -> None:
        self.user = create_user(username="streakuser")
        self.today = timezone.localdate()

    def _plant(self, *offsets: int) -> None:
        for offset in offsets:
            add_activity_day(
                user=self.user, activity_date=self.today - timedelta(days=offset)
            )

    def test_no_activity_means_zero(self) -> None:
        streak = streak_service.recalculate(user_id=self.user.id)
        self.assertEqual(streak.current_streak, 0)
        self.assertEqual(streak.longest_streak, 0)
        self.assertIsNone(streak.last_activity_date)

    def test_consecutive_days_count(self) -> None:
        self._plant(0, 1, 2)
        streak = streak_service.recalculate(user_id=self.user.id)
        self.assertEqual(streak.current_streak, 3)
        self.assertEqual(streak.longest_streak, 3)
        self.assertEqual(streak.last_activity_date, self.today)

    def test_yesterday_keeps_the_streak_alive(self) -> None:
        self._plant(1, 2)
        streak = streak_service.recalculate(user_id=self.user.id)
        self.assertEqual(streak.current_streak, 2)

    def test_a_gap_kills_the_current_streak_but_not_the_longest(self) -> None:
        # 5-day run long ago, then a gap, then 2 recent days.
        self._plant(10, 11, 12, 13, 14, 0, 1)
        streak = streak_service.recalculate(user_id=self.user.id)
        self.assertEqual(streak.current_streak, 2)
        self.assertEqual(streak.longest_streak, 5)

    def test_stale_activity_means_zero_current(self) -> None:
        self._plant(3, 4, 5)
        streak = streak_service.recalculate(user_id=self.user.id)
        self.assertEqual(streak.current_streak, 0)
        self.assertEqual(streak.longest_streak, 3)
        self.assertEqual(
            streak.last_activity_date, self.today - timedelta(days=3)
        )

    def test_recalc_is_stable(self) -> None:
        self._plant(0, 1)
        first = streak_service.recalculate(user_id=self.user.id)
        second = streak_service.recalculate(user_id=self.user.id)
        self.assertEqual(first.current_streak, second.current_streak)
        self.assertEqual(first.longest_streak, second.longest_streak)
