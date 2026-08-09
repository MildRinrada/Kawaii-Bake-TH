"""Unit tests for the pure scoring engine — no database."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.questions.constants import QuestionType
from apps.questions.selectors.answer_key import AnswerKey
from apps.quizzes.services.scoring_service import AnswerInput, grade_attempt


def _key(question_id: int, question_type: str, correct: set[int], all_ids: set[int]) -> AnswerKey:
    return AnswerKey(
        question_id=question_id,
        question_type=question_type,
        correct_choice_ids=frozenset(correct),
        all_choice_ids=frozenset(all_ids),
    )


class GradeAttemptTests(SimpleTestCase):
    """Exact-one, exact-set, skips, rounding and the pass boundary."""

    def test_single_choice_grades_exact_one(self) -> None:
        key = _key(1, QuestionType.SINGLE_CHOICE, {10}, {10, 11, 12})
        cases = [
            (frozenset({10}), True),
            (frozenset({11}), False),
            (frozenset({10, 11}), False),  # over-selection is wrong
            (frozenset(), False),  # skipped
        ]
        for selected, expected in cases:
            with self.subTest(selected=sorted(selected)):
                summary, results = grade_attempt(
                    answers=[AnswerInput(1, 1, selected)],
                    keys={1: key},
                    pass_percent=50,
                )
                self.assertEqual(results[0].was_correct, expected)

    def test_multiple_choice_is_exact_set_match(self) -> None:
        key = _key(1, QuestionType.MULTIPLE_CHOICE, {10, 11}, {10, 11, 12})
        cases = [
            (frozenset({10, 11}), True),
            (frozenset({10}), False),  # missing one — no partial credit
            (frozenset({10, 11, 12}), False),  # an incorrect one included
            (frozenset(), False),
        ]
        for selected, expected in cases:
            with self.subTest(selected=sorted(selected)):
                _, results = grade_attempt(
                    answers=[AnswerInput(1, 1, selected)],
                    keys={1: key},
                    pass_percent=50,
                )
                self.assertEqual(results[0].was_correct, expected)

    def test_summary_counts_points_and_percentage(self) -> None:
        keys = {
            1: _key(1, QuestionType.SINGLE_CHOICE, {10}, {10, 11}),
            2: _key(2, QuestionType.SINGLE_CHOICE, {20}, {20, 21}),
            3: _key(3, QuestionType.SINGLE_CHOICE, {30}, {30, 31}),
        }
        summary, _ = grade_attempt(
            answers=[
                AnswerInput(1, 2, frozenset({10})),  # correct, 2 points
                AnswerInput(2, 1, frozenset({21})),  # wrong
                AnswerInput(3, 1, frozenset()),  # skipped
            ],
            keys=keys,
            pass_percent=50,
        )
        self.assertEqual(summary.score, 2)
        self.assertEqual(summary.max_score, 4)
        self.assertEqual(summary.correct_count, 1)
        self.assertEqual(summary.incorrect_count, 2)
        self.assertEqual(summary.percentage, Decimal("50.00"))
        self.assertTrue(summary.passed)  # >= is passing

    def test_rounding_is_half_up_to_two_places(self) -> None:
        keys = {
            i: _key(i, QuestionType.SINGLE_CHOICE, {i * 10}, {i * 10, i * 10 + 1})
            for i in (1, 2, 3)
        }
        summary, _ = grade_attempt(
            answers=[
                AnswerInput(1, 1, frozenset({10})),
                AnswerInput(2, 1, frozenset({21})),
                AnswerInput(3, 1, frozenset({31})),
            ],
            keys=keys,
            pass_percent=34,
        )
        self.assertEqual(summary.percentage, Decimal("33.33"))
        self.assertFalse(summary.passed)

    def test_empty_attempt_scores_zero_without_dividing(self) -> None:
        summary, results = grade_attempt(answers=[], keys={}, pass_percent=70)
        self.assertEqual(summary.percentage, Decimal("0.00"))
        self.assertEqual(results, [])
        self.assertFalse(summary.passed)
