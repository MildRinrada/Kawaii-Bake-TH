"""Rule-registry integrity and the bilingual presentation contract."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.progress.tests.factories import complete_lesson_row
from apps.rewards.constants import (
    REASON_TEXT,
    REWARD_RULES,
    RewardReason,
    event_key,
)
from apps.rewards.services import reward_service
from apps.users.tests.factories import create_user

THAI_RANGE = range(0x0E00, 0x0E80)


def contains_thai(text: str) -> bool:
    return any(ord(char) in THAI_RANGE for char in text)


class RuleRegistryTests(SimpleTestCase):
    """The rules are complete, deterministic and honestly bilingual."""

    def test_every_reason_has_bilingual_text(self) -> None:
        for reason in RewardReason.values:
            self.assertIn(reason, REASON_TEXT)
            text = REASON_TEXT[reason]
            self.assertTrue(text.th)
            self.assertTrue(text.en)

    def test_thai_titles_are_actually_thai_not_fallbacks(self) -> None:
        for reason, text in REASON_TEXT.items():
            self.assertTrue(
                contains_thai(text.th),
                f"{reason} Thai title has no Thai characters: {text.th!r}",
            )
            self.assertNotEqual(text.th, text.en)

    def test_reward_values_are_positive_and_deterministic(self) -> None:
        self.assertEqual(REWARD_RULES[RewardReason.LESSON_COMPLETED], 5)
        self.assertEqual(REWARD_RULES[RewardReason.COURSE_COMPLETED], 50)
        for reason, amount in REWARD_RULES.items():
            self.assertGreater(amount, 0, reason)
            self.assertIn(reason, RewardReason.values)

    def test_spend_and_adjustment_are_not_claimable(self) -> None:
        self.assertNotIn(RewardReason.REWARD_SPENT, REWARD_RULES)
        self.assertNotIn(RewardReason.STAFF_ADJUSTMENT, REWARD_RULES)

    def test_event_key_is_stable(self) -> None:
        self.assertEqual(
            event_key(RewardReason.LESSON_COMPLETED, 42), "lesson_completed:42"
        )


class ClaimTests(TestCase):
    """Claiming settles identified facts exactly once each."""

    def setUp(self) -> None:
        self.instructor = create_user(username="rwteach")
        self.student = create_user(username="rwlearn")

    def test_claim_earns_for_completed_lesson(self) -> None:
        course = create_published_course(instructor=self.instructor)
        lesson = create_lesson(course=course)
        enroll_user(user=self.student, course=course)
        complete_lesson_row(user=self.student, lesson=lesson)

        result = reward_service.claim(user_id=self.student.id)
        self.assertEqual(result["claimed"], 1)
        self.assertEqual(
            result["points"], REWARD_RULES[RewardReason.LESSON_COMPLETED]
        )
        self.assertEqual(result["balance"], result["points"])

    def test_claim_twice_grants_nothing_new(self) -> None:
        course = create_published_course(instructor=self.instructor)
        lesson = create_lesson(course=course)
        enroll_user(user=self.student, course=course)
        complete_lesson_row(user=self.student, lesson=lesson)

        first = reward_service.claim(user_id=self.student.id)
        second = reward_service.claim(user_id=self.student.id)
        self.assertEqual(second["claimed"], 0)
        self.assertEqual(second["balance"], first["balance"])

    def test_claim_with_no_facts_is_flat_and_empty(self) -> None:
        # 5 identified-fact selectors + existing keys + summary read.
        with self.assertNumQueries(7):
            result = reward_service.claim(user_id=self.student.id)
        self.assertEqual(result, {"claimed": 0, "points": 0, "balance": 0})
