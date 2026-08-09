"""The reward API: ownership, permissions, Thai over HTTP, query counts."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.rewards.constants import RewardKind, RewardReason
from apps.rewards.repositories import reward_repository
from apps.rewards.selectors import reward_selector
from apps.users.tests.factories import create_user

SUMMARY_URL = "/api/v1/me/rewards/"
HISTORY_URL = "/api/v1/me/rewards/transactions/"
CLAIM_URL = "/api/v1/me/rewards/claim/"
ADJUST_URL = "/api/v1/rewards/adjustments/"


def earn(user, key: str, amount: int = 5):
    return reward_repository.apply_transaction(
        user_id=user.id,
        kind=RewardKind.EARN,
        reason_code=RewardReason.LESSON_COMPLETED,
        amount=amount,
        event_key=key,
    )[0]


class RewardApiTests(TestCase):
    """Owner-scoped reads and the claim door."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="rwapi")
        self.other = create_user(username="rwother")

    def test_anonymous_is_rejected(self) -> None:
        for url in (SUMMARY_URL, HISTORY_URL):
            self.assertIn(self.client.get(url).status_code, (401, 403))
        self.assertIn(self.client.post(CLAIM_URL).status_code, (401, 403))

    def test_summary_zeros_before_first_earn(self) -> None:
        self.client.force_login(self.user)
        payload = self.client.get(SUMMARY_URL).json()
        self.assertEqual(
            payload,
            {"balance": 0, "lifetime_earned": 0, "lifetime_spent": 0},
        )

    def test_summary_reflects_the_account(self) -> None:
        earn(self.user, "lesson_completed:1", 5)
        earn(self.user, "lesson_completed:2", 5)
        self.client.force_login(self.user)
        payload = self.client.get(SUMMARY_URL).json()
        self.assertEqual(payload["balance"], 10)
        self.assertEqual(payload["lifetime_earned"], 10)

    def test_history_is_own_rows_only_newest_first(self) -> None:
        earn(self.user, "lesson_completed:1")
        earn(self.user, "lesson_completed:2")
        earn(self.other, "lesson_completed:1")

        self.client.force_login(self.user)
        payload = self.client.get(HISTORY_URL).json()
        self.assertEqual(payload["count"], 2)
        keys = [item["reason"]["code"] for item in payload["results"]]
        self.assertEqual(keys, ["lesson_completed", "lesson_completed"])
        # Newest first, deterministically.
        afters = [item["balance_after"] for item in payload["results"]]
        self.assertEqual(afters, [10, 5])

    def test_other_user_sees_their_own_empty_history(self) -> None:
        earn(self.user, "lesson_completed:1")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(HISTORY_URL).json()["count"], 0)
        self.assertEqual(self.client.get(SUMMARY_URL).json()["balance"], 0)

    def test_thai_reason_survives_http(self) -> None:
        earn(self.user, "lesson_completed:1")
        self.client.force_login(self.user)
        item = self.client.get(HISTORY_URL).json()["results"][0]
        self.assertEqual(item["reason"]["title_th"], "เรียนจบบทเรียน")
        self.assertEqual(item["reason"]["title_en"], "Lesson completed")

    def test_no_email_and_no_internal_keys_in_payloads(self) -> None:
        earn(self.user, "lesson_completed:1")
        self.client.force_login(self.user)
        raw = self.client.get(HISTORY_URL).content.decode()
        self.assertNotIn("@example.com", raw)
        self.assertNotIn("event_key", raw)

    def test_claim_endpoint_is_idempotent(self) -> None:
        self.client.force_login(self.user)
        first = self.client.post(CLAIM_URL).json()
        second = self.client.post(CLAIM_URL).json()
        self.assertEqual(first["claimed"], 0)
        self.assertEqual(second, first)

    def test_history_pagination(self) -> None:
        for index in range(3):
            earn(self.user, f"lesson_completed:{index}")
        self.client.force_login(self.user)
        payload = self.client.get(HISTORY_URL, {"page_size": 2}).json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(len(payload["results"]), 2)
        self.assertIsNotNone(payload["next"])

    def test_unknown_query_param_rejected(self) -> None:
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(HISTORY_URL, {"kind": "earn"}).status_code, 400
        )

    def test_history_selector_query_count(self) -> None:
        earn(self.user, "lesson_completed:1")
        with self.assertNumQueries(1):
            list(reward_selector.list_transactions(user_id=self.user.id))


class AdjustmentApiTests(TestCase):
    """The staff door: permissioned, audited, Thai-preserving."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="rwadj")
        self.staff = create_user(username="rwadmin", is_staff=True)

    def test_non_staff_is_forbidden(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            ADJUST_URL,
            {"username": "rwadj", "amount": 10, "reason": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_adjustment_round_trips_thai(self) -> None:
        self.client.force_login(self.staff)
        response = self.client.post(
            ADJUST_URL,
            {
                "username": "rwadj",
                "amount": 40,
                "reason": "ชดเชยคะแนนจากระบบขัดข้อง",
                "idempotency_key": "ticket-1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["note"], "ชดเชยคะแนนจากระบบขัดข้อง")
        self.assertEqual(body["actor_handle"], "rwadmin")
        self.assertEqual(body["reason"]["title_th"], "ปรับปรุงโดยทีมงาน")

        # The target sees it in their own history, Thai intact.
        self.client.force_login(self.user)
        item = self.client.get(HISTORY_URL).json()["results"][0]
        self.assertEqual(item["note"], "ชดเชยคะแนนจากระบบขัดข้อง")
        self.assertEqual(self.client.get(SUMMARY_URL).json()["balance"], 40)

    def test_adjustment_replay_does_not_double(self) -> None:
        self.client.force_login(self.staff)
        payload = {
            "username": "rwadj",
            "amount": 40,
            "reason": "ชดเชย",
            "idempotency_key": "ticket-2",
        }
        self.client.post(ADJUST_URL, payload, format="json")
        self.client.post(ADJUST_URL, payload, format="json")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(SUMMARY_URL).json()["balance"], 40)

    def test_overdraw_is_a_409(self) -> None:
        self.client.force_login(self.staff)
        response = self.client.post(
            ADJUST_URL,
            {"username": "rwadj", "amount": -5, "reason": "หัก"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "insufficient_balance")

    def test_unknown_target_is_a_404(self) -> None:
        self.client.force_login(self.staff)
        response = self.client.post(
            ADJUST_URL,
            {"username": "ghost", "amount": 5, "reason": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_unknown_body_field_rejected(self) -> None:
        self.client.force_login(self.staff)
        response = self.client.post(
            ADJUST_URL,
            {"username": "rwadj", "amount": 5, "reason": "x", "boost": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
