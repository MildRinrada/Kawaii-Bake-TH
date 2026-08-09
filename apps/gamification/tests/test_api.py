"""API tests: summary, streak, recalculate, the public leaderboard."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.certificates.tests.factories import build_completed_course
from apps.gamification.constants import XPReason
from apps.gamification.services import xp_service
from apps.gamification.tests.factories import add_activity_day
from apps.users.tests.factories import create_user


class GamificationApiTests(TestCase):
    """The three owner endpoints."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="gapiuser")

    def test_anonymous_is_denied_on_owner_endpoints(self) -> None:
        paths = [
            ("get", "/api/v1/me/gamification/"),
            ("get", "/api/v1/me/streak/"),
            ("post", "/api/v1/me/gamification/recalculate/"),
        ]
        for method, path in paths:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)

    def test_fresh_user_summary_has_defaults(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/me/gamification/")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["level"]["current_level"], 1)
        self.assertEqual(body["level"]["total_xp"], 0)
        self.assertEqual(body["streak"]["current"], 0)
        self.assertEqual(body["recent_transactions"], [])

    def test_recalculate_builds_the_summary_from_facts(self) -> None:
        instructor = create_user(username="gapiinst")
        build_completed_course(student=self.user, instructor=instructor)
        add_activity_day(user=self.user, activity_date=timezone.localdate())

        self.client.force_login(self.user)
        response = self.client.post("/api/v1/me/gamification/recalculate/")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        # 1 lesson (10) + 1 course (100) = 110 → level 2.
        self.assertEqual(body["level"]["total_xp"], 110)
        self.assertEqual(body["level"]["current_level"], 2)
        self.assertGreaterEqual(body["streak"]["current"], 1)
        reasons = {row["reason"] for row in body["recent_transactions"]}
        self.assertEqual(reasons, {"lesson_completed", "course_completed"})

        # Idempotent: a second call changes nothing.
        again = self.client.post("/api/v1/me/gamification/recalculate/").json()
        self.assertEqual(again["level"]["total_xp"], 110)

    def test_my_streak_shape(self) -> None:
        today = timezone.localdate()
        add_activity_day(user=self.user, activity_date=today)
        add_activity_day(user=self.user, activity_date=today - timedelta(days=1))

        self.client.force_login(self.user)
        response = self.client.get("/api/v1/me/streak/")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["current"], 2)
        self.assertEqual(body["longest"], 2)
        self.assertEqual(body["last_activity"], today.isoformat())


class LeaderboardApiTests(TestCase):
    """The public read, its ordering and its query count."""

    def setUp(self) -> None:
        self.client = APIClient()

    def test_leaderboard_is_public_ordered_and_narrow(self) -> None:
        low = create_user(username="lblow")
        high = create_user(username="lbhigh")
        xp_service.award(user_id=low.id, reason=XPReason.REVIEW_WRITTEN)
        xp_service.award(user_id=high.id, reason=XPReason.COURSE_COMPLETED)

        response = self.client.get("/api/v1/leaderboard/")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["results"][0]["public_handle"], "lbhigh")
        self.assertEqual(body["results"][0]["total_xp"], 100)
        self.assertEqual(body["results"][0]["level"], 2)
        # Handle, level, XP — nothing else leaks.
        self.assertEqual(
            set(body["results"][0]), {"public_handle", "level", "total_xp"}
        )
        self.assertNotIn(high.email, str(body))

    def test_leaderboard_query_count_is_flat(self) -> None:
        for index in range(8):
            user = create_user(username=f"lbflat{index}")
            xp_service.award(
                user_id=user.id, reason=XPReason.LESSON_COMPLETED
            )

        # Anonymous: count + one page with the user join — no per-row query.
        with self.assertNumQueries(2):
            response = self.client.get("/api/v1/leaderboard/")
        self.assertEqual(response.json()["count"], 8)
