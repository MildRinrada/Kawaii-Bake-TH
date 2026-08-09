"""Quiz lifecycle transitions.

Same state machine as recipes and courses: every transition reversible, only
DELETE is terminal (and blocked once attempts exist), publish is idempotent
and re-validates on the archived → published path. ``published_at`` is
stamped once and freezes the slug.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.questions.selectors import question_selector
from apps.quizzes.constants import QuizStatus
from apps.quizzes.exceptions import QuizNotVisibleError
from apps.quizzes.models import Quiz
from apps.quizzes.permissions.quiz_permissions import can_change_status
from apps.quizzes.repositories import quiz_repository
from apps.quizzes.selectors import quiz_selector
from apps.quizzes.validators.publish_validator import assert_publishable

logger = logging.getLogger("kawaiibake.quizzes")


def _require_transitionable(*, slug: str, viewer_id: int, viewer_is_staff: bool) -> Quiz:
    """Fetch a quiz whose status the caller may change."""
    quiz = quiz_selector.get_editable_quiz(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if quiz is None or not can_change_status(
        owner_id=quiz.owner_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise QuizNotVisibleError
    return quiz


def publish(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Quiz:
    """Publish a quiz after checking completeness.

    "Every question has valid answers" is checked by the **questions** app
    against what is actually stored — the domain that owns the answer rules
    judges them; this app only forwards the verdict.

    Idempotent; ``published_at`` is stamped only the first time.

    Raises:
        QuizNotVisibleError: If absent or not the caller's to change.
        QuizNotPublishableError: If incomplete — every failure in ``details``.
    """
    quiz = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if quiz.status == QuizStatus.PUBLISHED:
        return quiz

    composition = quiz_selector.list_composition(quiz_id=quiz.pk)
    question_ids = [row.question_id for row in composition]
    assert_publishable(
        quiz,
        question_count=len(composition),
        answer_problems=question_selector.answer_validation_problems(
            ids=question_ids
        ),
    )

    changes: dict[str, object] = {"status": QuizStatus.PUBLISHED}
    if quiz.published_at is None:
        changes["published_at"] = timezone.now()

    quiz_repository.update_quiz(quiz=quiz, changes=changes)
    logger.info("quiz_published quiz_id=%s by=%s", quiz.pk, viewer_id)
    return quiz


def unpublish(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Quiz:
    """Return a quiz to draft — the hard kill switch.

    Open attempts on it may still be submitted: an attempt that exists is
    access already granted, and a student mid-quiz must not lose their work.
    ``published_at`` is retained so the slug stays frozen.
    """
    quiz = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if quiz.status != QuizStatus.DRAFT:
        quiz_repository.update_quiz(quiz=quiz, changes={"status": QuizStatus.DRAFT})
        logger.info("quiz_unpublished quiz_id=%s by=%s", quiz.pk, viewer_id)
    return quiz


def archive(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> Quiz:
    """Archive a quiz.

    Archived quizzes leave every listing and accept no new attempts, but stay
    **readable to anyone who has attempted them** — results history must not
    vanish because the instructor tidied up.
    """
    quiz = _require_transitionable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if quiz.status != QuizStatus.ARCHIVED:
        quiz_repository.update_quiz(quiz=quiz, changes={"status": QuizStatus.ARCHIVED})
        logger.info("quiz_archived quiz_id=%s by=%s", quiz.pk, viewer_id)
    return quiz
