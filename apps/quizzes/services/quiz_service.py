"""Business logic for quizzes: CRUD and composition."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from django.db import transaction
from django.db.models import ProtectedError

from apps.questions.selectors import question_selector
from apps.quizzes.constants import MAX_QUESTIONS_PER_QUIZ, QuizStatus
from apps.quizzes.exceptions import (
    InvalidQuizQuestionError,
    QuizHasAttemptsError,
    QuizNotVisibleError,
    QuizSlugImmutableError,
    QuizSlugTakenError,
)
from apps.quizzes.models import Quiz
from apps.quizzes.permissions.quiz_permissions import can_delete_quiz, can_edit_quiz
from apps.quizzes.repositories import quiz_repository
from apps.quizzes.selectors import quiz_selector
from apps.quizzes.utils import build_quiz_slug_base

logger = logging.getLogger("kawaiibake.quizzes")

# `status` is deliberately absent: publishing must run the completeness checks
# in publish_service. `visibility` is a plain field with no precondition.
QUIZ_EDITABLE_FIELDS = frozenset(
    {"title", "description", "pass_percent", "visibility"}
)


def create_quiz(*, owner_id: int, data: Mapping[str, Any]) -> Quiz:
    """Create a quiz as a draft, optionally with an initial composition.

    Args:
        owner_id: Primary key of the owner.
        data: Validated payload.

    Returns:
        The created quiz, re-read through the detail selector.

    Raises:
        InvalidQuizQuestionError: If any composed question is unusable.
    """
    question_ids = list(data.get("question_ids") or [])
    _validate_composition(question_ids=question_ids, viewer_id=owner_id)

    with transaction.atomic():
        quiz = quiz_repository.create_quiz(
            owner_id=owner_id,
            slug_base=build_quiz_slug_base(data["title"]),
            **{k: v for k, v in data.items() if k in QUIZ_EDITABLE_FIELDS},
        )
        if question_ids:
            quiz_repository.set_composition(quiz=quiz, question_ids=question_ids)

    logger.info("quiz_created quiz_id=%s by=%s", quiz.pk, owner_id)
    return _require_detail(slug=quiz.slug, viewer_id=owner_id)


def update_quiz(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False, data: Mapping[str, Any]
) -> Quiz:
    """Apply a partial update to a quiz, including composition replacement.

    ``question_ids`` replaces the whole composition in submitted order —
    reordering **is** this operation, no separate endpoint. Safe because
    nothing references composition rows (attempts snapshot at start).

    Args:
        slug: The quiz slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload; absent keys are unchanged.

    Returns:
        The updated quiz, re-read through the detail selector.

    Raises:
        QuizNotVisibleError: If absent or not the caller's to edit.
        QuizSlugImmutableError: If the slug of a published quiz would change.
        QuizSlugTakenError: If the requested slug is in use.
        InvalidQuizQuestionError: If any composed question is unusable, or a
            published quiz would be left without questions.
    """
    quiz = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    if "slug" in data and data["slug"] != quiz.slug:
        if quiz.slug_is_frozen and not viewer_is_staff:
            raise QuizSlugImmutableError
        if quiz_selector.slug_exists(slug=data["slug"], exclude_pk=quiz.pk):
            raise QuizSlugTakenError(details={"slug": ["Already in use."]})

    question_ids: list[int] | None = None
    if "question_ids" in data:
        question_ids = list(data["question_ids"] or [])
        _validate_composition(
            question_ids=question_ids,
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
        )
        if not question_ids and quiz.status == QuizStatus.PUBLISHED:
            raise InvalidQuizQuestionError(
                details={
                    "question_ids": [
                        "A published quiz must keep at least one question. "
                        "Unpublish it first."
                    ]
                }
            )

    changes = {k: v for k, v in data.items() if k in QUIZ_EDITABLE_FIELDS}
    if "slug" in data:
        changes["slug"] = data["slug"]

    with transaction.atomic():
        quiz_repository.update_quiz(quiz=quiz, changes=changes)
        if question_ids is not None:
            quiz_repository.set_composition(quiz=quiz, question_ids=question_ids)

    return _require_detail(
        slug=changes.get("slug", quiz.slug),
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    )


def delete_quiz(*, slug: str, viewer_id: int, viewer_is_staff: bool = False) -> None:
    """Permanently delete a quiz with no attempt history.

    Archiving is the only exit for a quiz that has been attempted — history
    is permanent.

    Args:
        slug: The quiz slug.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        QuizNotVisibleError: If absent or not the caller's to delete.
        QuizHasAttemptsError: If any attempt exists.
    """
    quiz = _require_editable(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if not can_delete_quiz(
        owner_id=quiz.owner_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise QuizNotVisibleError

    try:
        quiz_repository.delete_quiz(quiz=quiz)
    except ProtectedError as error:
        raise QuizHasAttemptsError from error
    logger.info("quiz_deleted quiz_id=%s by=%s", quiz.pk, viewer_id)


def get_quiz(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Quiz:
    """Fetch a quiz for display.

    Raises:
        QuizNotVisibleError: If absent or hidden.
    """
    return _require_detail(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def get_quiz_with_questions(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> tuple[Quiz, list[question_selector.TakerQuestionDTO], dict[int, int]]:
    """Fetch a quiz plus its questions in the taker-safe shape.

    One shape for every viewer — the DTOs structurally cannot carry
    ``is_correct``, so there is no owner variant to fail open. Owners read
    correctness through their own bank endpoints.

    Args:
        slug: The quiz slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The quiz, its questions in composition order, and a mapping of
        question id to points.

    Raises:
        QuizNotVisibleError: If absent or hidden.
    """
    quiz = _require_detail(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    composition = quiz_selector.list_composition(quiz_id=quiz.pk)
    dtos = question_selector.list_taker_questions(
        ids=[row.question_id for row in composition]
    )
    ordered = [dtos[row.question_id] for row in composition if row.question_id in dtos]
    points = {row.question_id: row.points for row in composition}
    return quiz, ordered, points


def _validate_composition(
    *,
    question_ids: Sequence[int],
    viewer_id: int,
    viewer_is_staff: bool = False,
) -> None:
    """Check a composition payload: size, uniqueness and usability.

    A usable question is one the composer owns (or staff). Unknown and
    foreign ids are reported identically — distinguishing them would confirm
    foreign ids exist.

    Raises:
        InvalidQuizQuestionError: With the exact diff in ``details``.
    """
    ids = list(question_ids)
    problems: dict[str, object] = {}

    if len(ids) > MAX_QUESTIONS_PER_QUIZ:
        problems["question_ids"] = [
            f"A quiz can hold at most {MAX_QUESTIONS_PER_QUIZ} questions."
        ]

    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems["duplicate_ids"] = duplicates

    refs = question_selector.list_refs_by_ids(
        ids=ids, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    unusable = sorted(set(ids) - set(refs))
    if unusable:
        problems["unknown_ids"] = unusable

    if problems:
        raise InvalidQuizQuestionError(details=problems)


def _require_detail(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Quiz:
    """Fetch a quiz or raise the 404 domain error."""
    quiz = quiz_selector.get_quiz_detail(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if quiz is None:
        raise QuizNotVisibleError
    return quiz


def _require_editable(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> Quiz:
    """Fetch a quiz the caller may modify; "not yours" is the same 404."""
    quiz = quiz_selector.get_editable_quiz(
        slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if quiz is None or not can_edit_quiz(
        owner_id=quiz.owner_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ):
        raise QuizNotVisibleError
    return quiz
