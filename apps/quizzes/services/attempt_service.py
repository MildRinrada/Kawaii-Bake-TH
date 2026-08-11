"""Business logic for quiz attempts: start, submit, abandon.

The transaction in :func:`start_attempt` is the heart of Phase 4's integrity
story  freeze and snapshot commit or roll back **together**:

1. resolve the quiz through visibility (hidden ⇒ 404, fail-closed)
2. require ``published`` (400 otherwise)
3. return any existing open attempt (idempotent, like enroll)
4. read the composition
5. ``question_service.freeze_questions()``  the allowed-direction push;
   this app knows *why* (answers are about to reference these questions),
   the questions app records *that*
6. create the attempt (``max_score`` stamped now)
7. create the empty answer rows (position + ``points_possible`` snapshot)

After commit, grading depends only on immutable data.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from django.db import transaction

from apps.questions.selectors import answer_key, question_selector
from apps.questions.services import question_service
from apps.quizzes.constants import QuizStatus
from apps.quizzes.exceptions import (
    AttemptAlreadySubmittedError,
    AttemptNotFoundError,
    InvalidSubmissionError,
    NoOpenAttemptError,
    QuizNotAvailableError,
    QuizNotVisibleError,
)
from apps.quizzes.models import QuizAttempt
from apps.quizzes.repositories import attempt_repository
from apps.quizzes.selectors import attempt_selector, quiz_selector
from apps.quizzes.selectors.quiz_selector import QuizRef
from apps.quizzes.services import scoring_service
from apps.quizzes.services.scoring_service import AnswerInput, QuestionResult

logger = logging.getLogger("kawaiibake.quizzes")


def start_attempt(*, user_id: int, slug: str) -> tuple[QuizAttempt, bool]:
    """Start (or resume) an attempt. Idempotent.

    Args:
        user_id: Primary key of the taker.
        slug: The quiz slug.

    Returns:
        The attempt and whether it was newly created.

    Raises:
        QuizNotVisibleError: If the quiz is absent or hidden (404).
        QuizNotAvailableError: If the quiz is not published, or has no
            questions to ask.
    """
    quiz = _require_quiz_ref(slug=slug, viewer_id=user_id)
    if quiz.status != QuizStatus.PUBLISHED:
        raise QuizNotAvailableError

    with transaction.atomic():
        existing = attempt_selector.get_open_attempt(user_id=user_id, quiz_id=quiz.id)
        if existing is not None:
            return existing, False

        composition = quiz_selector.list_composition(quiz_id=quiz.id)
        if not composition:
            raise QuizNotAvailableError

        question_service.freeze_questions(
            question_ids=[row.question_id for row in composition]
        )
        attempt = attempt_repository.create_attempt_with_snapshot(
            user_id=user_id, quiz_id=quiz.id, composition=composition
        )

    if attempt is None:
        # Lost a double-start race; the winner's attempt is the open one.
        attempt = attempt_selector.get_open_attempt(user_id=user_id, quiz_id=quiz.id)
        if attempt is None:  # pragma: no cover - needs a third racer
            raise NoOpenAttemptError
        return attempt, False

    logger.info(
        "attempt_started attempt_id=%s quiz_id=%s user_id=%s",
        attempt.pk,
        quiz.id,
        user_id,
    )
    return attempt, True


def submit_attempt(
    *, user_id: int, slug: str, answers: Sequence[Mapping[str, Any]]
) -> tuple[QuizAttempt, list[QuestionResult]]:
    """Grade and close the caller's open attempt on a quiz.

    Grading reads only the attempt's snapshot rows and the frozen questions'
    answer keys  never the live composition, which may have changed since
    start. Questions omitted from the payload are graded as skipped
    (incorrect). Deliberately **not** idempotent: a second submit may carry
    different answers, so it is 409, unlike enroll.

    Args:
        user_id: Primary key of the taker.
        slug: The quiz slug.
        answers: ``{question_id, choice_ids}`` mappings.

    Returns:
        The graded attempt and the per-question results in snapshot order.

    Raises:
        QuizNotVisibleError: If the quiz is absent or hidden (404).
        NoOpenAttemptError: If the caller has nothing in progress.
        AttemptAlreadySubmittedError: If a concurrent submit won the race.
        InvalidSubmissionError: If the payload does not match the snapshot 
            the exact diff is in ``details``.
    """
    quiz = _require_quiz_ref(slug=slug, viewer_id=user_id)

    attempt = attempt_selector.get_open_attempt(user_id=user_id, quiz_id=quiz.id)
    if attempt is None:
        raise NoOpenAttemptError

    snapshot = list(attempt.answers.all())
    keys = answer_key.get_answer_keys(ids=[row.question_id for row in snapshot])
    selections = _validate_submission(snapshot=snapshot, answers=answers, keys=keys)
    summary, results = scoring_service.grade_attempt(
        answers=[
            AnswerInput(
                question_id=row.question_id,
                points_possible=row.points_possible,
                selected_choice_ids=selections.get(row.question_id, frozenset()),
            )
            for row in snapshot
        ],
        keys=keys,
        pass_percent=quiz.pass_percent,
    )

    transitioned = attempt_repository.submit_attempt(
        attempt=attempt,
        score=summary.score,
        correct_count=summary.correct_count,
        incorrect_count=summary.incorrect_count,
        percentage=summary.percentage,
        passed=summary.passed,
        results={
            result.question_id: (
                result.was_correct,
                result.points_awarded,
                sorted(selections.get(result.question_id, frozenset())),
            )
            for result in results
        },
    )
    if not transitioned:
        raise AttemptAlreadySubmittedError

    logger.info(
        "attempt_submitted attempt_id=%s quiz_id=%s user_id=%s score=%s/%s passed=%s",
        attempt.pk,
        quiz.id,
        user_id,
        summary.score,
        summary.max_score,
        summary.passed,
    )
    refreshed = attempt_selector.get_attempt(attempt_id=attempt.pk, user_id=user_id)
    return refreshed if refreshed is not None else attempt, results


def abandon_attempt(*, user_id: int, slug: str, attempt_id: int) -> None:
    """Delete the caller's own in-progress attempt.

    Submitted attempts are history and cannot be deleted. Any freezing the
    start performed remains  freezing is monotonic, and over-freezing is the
    safe direction.

    Args:
        user_id: Primary key of the caller.
        slug: The quiz slug (existence gate only).
        attempt_id: Primary key of the attempt.

    Raises:
        QuizNotVisibleError: If the quiz is absent or hidden (404).
        AttemptNotFoundError: If the attempt is absent or someone else's.
        AttemptAlreadySubmittedError: If the attempt was already submitted.
    """
    _require_quiz_ref(slug=slug, viewer_id=user_id)

    deleted = attempt_repository.abandon_open_attempt(
        user_id=user_id, attempt_id=attempt_id
    )
    if deleted:
        logger.info("attempt_abandoned attempt_id=%s user_id=%s", attempt_id, user_id)
        return

    existing = attempt_selector.get_attempt(attempt_id=attempt_id, user_id=user_id)
    if existing is None:
        raise AttemptNotFoundError
    raise AttemptAlreadySubmittedError


def get_attempt(
    *, user_id: int, slug: str, attempt_id: int, viewer_is_staff: bool = False
) -> QuizAttempt:
    """Fetch one attempt with its breakdown, for its owner or staff.

    Raises:
        QuizNotVisibleError: If the quiz is absent or hidden (404).
        AttemptNotFoundError: If absent, someone else's, or another quiz's.
    """
    quiz = _require_quiz_ref(
        slug=slug, viewer_id=user_id, viewer_is_staff=viewer_is_staff
    )
    attempt = attempt_selector.get_attempt(
        attempt_id=attempt_id, user_id=user_id, viewer_is_staff=viewer_is_staff
    )
    if attempt is None or attempt.quiz_id != quiz.id:
        raise AttemptNotFoundError
    return attempt


def require_visible_quiz(
    *, user_id: int, slug: str, viewer_is_staff: bool = False
) -> QuizRef:
    """Resolve a quiz for an attempt-scoped read, or raise the 404.

    Args:
        user_id: Primary key of the viewer.
        slug: The quiz slug.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The quiz reference.

    Raises:
        QuizNotVisibleError: If the quiz is absent or hidden.
    """
    return _require_quiz_ref(
        slug=slug, viewer_id=user_id, viewer_is_staff=viewer_is_staff
    )


def review_context(
    *, attempt: QuizAttempt
) -> tuple[dict[int, question_selector.TakerQuestionDTO], dict[int, str]]:
    """Fetch what a result review needs: taker-shaped questions, explanations.

    Explanations are returned only for **submitted** attempts  they often
    paraphrase the answer.

    Args:
        attempt: The attempt being reviewed, with answers prefetched.

    Returns:
        Taker DTOs and explanations, both keyed by question id.
    """
    ids = [answer.question_id for answer in attempt.answers.all()]
    questions = question_selector.list_taker_questions(ids=ids)
    explanations = (
        question_selector.list_explanations(ids=ids) if attempt.is_submitted else {}
    )
    return questions, explanations


def _validate_submission(
    *,
    snapshot: Sequence[Any],
    answers: Sequence[Mapping[str, Any]],
    keys: Mapping[int, answer_key.AnswerKey],
) -> dict[int, frozenset[int]]:
    """Check a submission against the attempt snapshot.

    Returns:
        Selected choice ids per question id.

    Raises:
        InvalidSubmissionError: With the exact diff in ``details``.
    """
    snapshot_ids = {row.question_id for row in snapshot}
    problems: dict[str, list[int]] = {}
    selections: dict[int, frozenset[int]] = {}

    submitted_ids = [int(answer["question_id"]) for answer in answers]
    duplicates = sorted({i for i in submitted_ids if submitted_ids.count(i) > 1})
    unknown = sorted(set(submitted_ids) - snapshot_ids)
    if duplicates:
        problems["duplicate_question_ids"] = duplicates
    if unknown:
        problems["unknown_question_ids"] = unknown

    if not problems:
        invalid_choices: list[int] = []
        for answer in answers:
            question_id = int(answer["question_id"])
            choice_ids = frozenset(int(c) for c in answer.get("choice_ids", ()))
            valid = keys[question_id].all_choice_ids
            if not choice_ids <= valid:
                invalid_choices.extend(sorted(choice_ids - valid))
            selections[question_id] = choice_ids
        if invalid_choices:
            problems["unknown_choice_ids"] = sorted(set(invalid_choices))

    if problems:
        raise InvalidSubmissionError(details=problems)
    return selections


def _require_quiz_ref(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> QuizRef:
    """Resolve a quiz slug through visibility or raise the 404."""
    quiz = quiz_selector.get_quiz_ref(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if quiz is None:
        raise QuizNotVisibleError
    return quiz
