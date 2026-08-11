"""Grading  pure functions, no ORM, no clock, no HTTP.

One grader per question type, held in a registry: a future type (short
answer, AI evaluation, matching…) is one new entry plus its validator, with
no change to the engine. Grading consumes only two inputs  the attempt's
**snapshot** (question order and points, fixed at start) and the bank's
**answer keys** (fixed by freezing, also at start)  so nothing an instructor
does mid-attempt can change a result.

No partial credit in this phase: multiple choice is exact-set match. Negative
scoring and weighted marks are future work; ``points_possible`` already flows
through, so weights are an authoring change, not an engine change.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from apps.questions.constants import QuestionType
from apps.questions.selectors.answer_key import AnswerKey


@dataclass(frozen=True)
class AnswerInput:
    """One question's snapshot entry plus the taker's selection."""

    question_id: int
    points_possible: int
    selected_choice_ids: frozenset[int]


@dataclass(frozen=True)
class QuestionResult:
    """The graded outcome for one question."""

    question_id: int
    was_correct: bool
    points_possible: int
    points_awarded: int


@dataclass(frozen=True)
class ScoreSummary:
    """The graded outcome for one attempt."""

    score: int
    max_score: int
    correct_count: int
    incorrect_count: int
    percentage: Decimal
    passed: bool


def _grade_exact_one(selected: frozenset[int], key: AnswerKey) -> bool:
    """Single choice / true-false: the one correct choice, and only it."""
    return selected == key.correct_choice_ids and len(selected) == 1


def _grade_exact_set(selected: frozenset[int], key: AnswerKey) -> bool:
    """Multiple choice: every correct choice, no incorrect one, not empty."""
    return bool(selected) and selected == key.correct_choice_ids


GRADERS: dict[str, Callable[[frozenset[int], AnswerKey], bool]] = {
    QuestionType.SINGLE_CHOICE: _grade_exact_one,
    QuestionType.TRUE_FALSE: _grade_exact_one,
    QuestionType.MULTIPLE_CHOICE: _grade_exact_set,
}


def grade_attempt(
    *,
    answers: Sequence[AnswerInput],
    keys: Mapping[int, AnswerKey],
    pass_percent: int,
) -> tuple[ScoreSummary, list[QuestionResult]]:
    """Grade a whole attempt.

    A skipped question (empty selection) is graded incorrect and awards
    nothing  skipping is answering wrong, not shrinking the quiz.

    Args:
        answers: The snapshot rows with the taker's selections.
        keys: Answer keys, keyed by question id.
        pass_percent: The quiz's pass mark.

    Returns:
        The attempt summary and the per-question results, in snapshot order.
    """
    results: list[QuestionResult] = []
    score = 0
    max_score = 0
    correct = 0

    for answer in answers:
        key = keys[answer.question_id]
        grader = GRADERS[key.question_type]
        was_correct = grader(answer.selected_choice_ids, key)
        awarded = answer.points_possible if was_correct else 0

        results.append(
            QuestionResult(
                question_id=answer.question_id,
                was_correct=was_correct,
                points_possible=answer.points_possible,
                points_awarded=awarded,
            )
        )
        score += awarded
        max_score += answer.points_possible
        correct += int(was_correct)

    percentage = _percentage(score=score, max_score=max_score)
    summary = ScoreSummary(
        score=score,
        max_score=max_score,
        correct_count=correct,
        incorrect_count=len(results) - correct,
        percentage=percentage,
        passed=percentage >= pass_percent,
    )
    return summary, results


def _percentage(*, score: int, max_score: int) -> Decimal:
    """Score as a percentage, two decimal places, half-up."""
    if max_score <= 0:
        return Decimal("0.00")
    raw = Decimal(score * 100) / Decimal(max_score)
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
