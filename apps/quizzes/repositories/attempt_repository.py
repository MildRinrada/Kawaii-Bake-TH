"""Write-side database access for quiz attempts.

The snapshot machinery lives here: attempt rows and their empty answer rows
are created together at start, and grading results are persisted behind a
conditional status transition so an attempt can never be graded twice.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.quizzes.constants import AttemptStatus
from apps.quizzes.models import QuizAttempt, QuizAttemptAnswer
from apps.quizzes.selectors.quiz_selector import CompositionRow


def create_attempt_with_snapshot(
    *, user_id: int, quiz_id: int, composition: Sequence[CompositionRow]
) -> QuizAttempt | None:
    """Create an attempt and its composition snapshot atomically.

    One empty :class:`QuizAttemptAnswer` row per composition entry, with
    ``position`` and ``points_possible`` copied now — after this moment,
    grading never reads the live composition again. ``max_score`` is stamped
    here for the same reason.

    Args:
        user_id: Primary key of the user.
        quiz_id: Primary key of the quiz.
        composition: The quiz's composition rows, in order.

    Returns:
        The created attempt, or ``None`` when the partial unique constraint
        reports a concurrent open attempt — the caller re-fetches.
    """
    try:
        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                user_id=user_id,
                quiz_id=quiz_id,
                status=AttemptStatus.IN_PROGRESS,
                started_at=timezone.now(),
                max_score=sum(row.points for row in composition),
            )
            QuizAttemptAnswer.objects.bulk_create(
                QuizAttemptAnswer(
                    attempt=attempt,
                    question_id=row.question_id,
                    position=row.position,
                    points_possible=row.points,
                )
                for row in composition
            )
            return attempt
    except IntegrityError:
        return None


def submit_attempt(
    *,
    attempt: QuizAttempt,
    score: int,
    correct_count: int,
    incorrect_count: int,
    percentage: object,
    passed: bool,
    results: Mapping[int, tuple[bool, int, Sequence[int]]],
) -> bool:
    """Persist grading results behind the one-shot status transition.

    The conditional UPDATE on ``status = in_progress`` is the arbiter: of two
    racing submits, exactly one affects a row; the loser gets ``False`` and
    the service raises 409. Selections are inserted through the M2M through
    table in one bulk write — answer rows start empty, so there is nothing to
    clear first.

    Args:
        attempt: The open attempt being submitted.
        score: Total points awarded.
        correct_count: Questions answered correctly.
        incorrect_count: Questions answered incorrectly (including skipped).
        percentage: Score as a percentage of ``max_score``.
        passed: Whether the percentage met the quiz's pass mark.
        results: Per-question ``(was_correct, points_awarded, selected_choice_ids)``.

    Returns:
        ``True`` when this call performed the transition.
    """
    with transaction.atomic():
        transitioned = QuizAttempt.objects.filter(
            pk=attempt.pk, status=AttemptStatus.IN_PROGRESS
        ).update(
            status=AttemptStatus.SUBMITTED,
            submitted_at=timezone.now(),
            score=score,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            percentage=percentage,
            passed=passed,
            updated_at=timezone.now(),
        )
        if transitioned != 1:
            return False

        answers = list(attempt.answers.all())
        selections = []
        through = QuizAttemptAnswer.selected_choices.through
        for answer in answers:
            was_correct, points_awarded, selected_ids = results[answer.question_id]
            answer.was_correct = was_correct
            answer.points_awarded = points_awarded
            selections.extend(
                through(quizattemptanswer_id=answer.pk, answerchoice_id=choice_id)
                for choice_id in selected_ids
            )
        QuizAttemptAnswer.objects.bulk_update(
            answers, ["was_correct", "points_awarded"]
        )
        through.objects.bulk_create(selections)
        return True


def abandon_open_attempt(*, user_id: int, attempt_id: int) -> int:
    """Delete the user's own in-progress attempt.

    Conditional on ownership **and** status in one statement, so a concurrent
    submit cannot lose history: once submitted, the row no longer matches.
    Snapshot answer rows cascade. Any freeze the start performed remains —
    freezing is monotonic and over-freezing is the safe direction.

    Args:
        user_id: Primary key of the user.
        attempt_id: Primary key of the attempt.

    Returns:
        How many attempts were deleted (0 or 1).
    """
    deleted, _ = QuizAttempt.objects.filter(
        pk=attempt_id, user_id=user_id, status=AttemptStatus.IN_PROGRESS
    ).delete()
    return deleted
