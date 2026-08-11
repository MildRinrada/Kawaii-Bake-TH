"""Business logic for the question bank."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from django.db import transaction
from django.db.models import ProtectedError

from apps.questions.exceptions import (
    InvalidQuestionChoicesError,
    QuestionFrozenError,
    QuestionInUseError,
    QuestionNotFoundError,
)
from apps.questions.models import Question
from apps.questions.repositories import question_repository
from apps.questions.selectors import question_selector
from apps.questions.validators import question_validator

logger = logging.getLogger("kawaiibake.questions")

# Frozen questions lock exactly what was asked and graded. Everything else 
# explanation (a post-submit learning aid), difficulty (bank metadata), tags 
# stays editable forever: organising the bank is not rewriting history.
FROZEN_LOCKED_FIELDS = frozenset({"text", "question_type", "choices"})
QUESTION_EDITABLE_FIELDS = frozenset(
    {"text", "question_type", "explanation", "difficulty"}
)


def create_question(*, author_id: int, data: Mapping[str, Any]) -> Question:
    """Create a bank question with its choices.

    Args:
        author_id: Primary key of the author.
        data: Validated payload, including ``choices`` and optional ``tags``.

    Returns:
        The created question, re-read with choices and tags loaded.

    Raises:
        InvalidQuestionChoicesError: If the choices break the type's rules.
    """
    question_validator.assert_valid_choices(
        question_type=data["question_type"], choices=data["choices"]
    )
    tag_ids = question_repository.get_or_create_tags(names=data.get("tags") or [])

    question = question_repository.create_question(
        author_id=author_id,
        choices=data["choices"],
        tag_ids=tag_ids,
        **{k: v for k, v in data.items() if k in QUESTION_EDITABLE_FIELDS},
    )
    logger.info("question_created question_id=%s by=%s", question.pk, author_id)
    return _require_own(question_id=question.pk, viewer_id=author_id)


def update_question(
    *,
    question_id: int,
    viewer_id: int,
    viewer_is_staff: bool = False,
    data: Mapping[str, Any],
) -> Question:
    """Apply a partial update, honouring the frozen gate.

    Content fields (text, type, choices) require the optimistic edit gate: a
    conditional UPDATE on ``frozen_at IS NULL`` that doubles as the row lock
    serializing this edit against a concurrent attempt-start freeze. Metadata
    fields (explanation, difficulty, tags) skip the gate entirely.

    Args:
        question_id: Primary key of the question.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload; absent keys are unchanged.

    Returns:
        The updated question, re-read with choices and tags loaded.

    Raises:
        QuestionNotFoundError: If absent or not the caller's.
        QuestionFrozenError: If content changes hit a frozen question.
        InvalidQuestionChoicesError: If the resulting choices are invalid.
    """
    question = _require_own(
        question_id=question_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    new_type = data.get("question_type", question.question_type)
    if "question_type" in data and new_type != question.question_type and "choices" not in data:
        raise InvalidQuestionChoicesError(
            details={"choices": ["Provide choices when changing the question type."]}
        )
    if "choices" in data:
        question_validator.assert_valid_choices(
            question_type=new_type, choices=data["choices"]
        )

    touches_content = bool(FROZEN_LOCKED_FIELDS & set(data.keys()))
    changes = {
        k: v
        for k, v in data.items()
        if k in QUESTION_EDITABLE_FIELDS and k != "choices"
    }

    with transaction.atomic():
        if touches_content and not question_repository.acquire_edit_gate(
            question_id=question.pk
        ):
            # The gate refused: frozen (409) or deleted underneath us (404).
            if Question.objects.filter(pk=question.pk).exists():
                raise QuestionFrozenError
            raise QuestionNotFoundError
        question_repository.update_question(question=question, changes=changes)
        if "choices" in data:
            question_repository.replace_choices(
                question=question, choices=data["choices"]
            )
        if "tags" in data:
            tag_ids = question_repository.get_or_create_tags(names=data["tags"] or [])
            question.tags.set(tag_ids)

    return _require_own(
        question_id=question.pk, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def delete_question(
    *, question_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Delete a question that is neither frozen nor referenced by a quiz.

    Args:
        question_id: Primary key of the question.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        QuestionNotFoundError: If absent or not the caller's.
        QuestionFrozenError: If the question has attempt history.
        QuestionInUseError: If a quiz still references it.
    """
    question = _require_own(
        question_id=question_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    try:
        with transaction.atomic():
            if not question_repository.acquire_edit_gate(question_id=question.pk):
                raise QuestionFrozenError
            question_repository.delete_question(question=question)
    except ProtectedError as error:
        raise QuestionInUseError from error
    logger.info("question_deleted question_id=%s by=%s", question_id, viewer_id)


def freeze_questions(*, question_ids: Sequence[int]) -> None:
    """Permanently freeze questions' content. **Idempotent.**

    Public cross-app write API  the quizzes app calls this at attempt start,
    inside the attempt's transaction (the counter-push mechanism of ADR 0009,
    carrying a timestamp instead of a number). The caller knows *why*; this
    app records *that*.

    Already-frozen questions are a no-op success, never a conflict: every
    second student starting the same quiz meets questions the first student
    froze, and that is the desired end state. The only failure is a question
    that does not exist.

    Args:
        question_ids: Primary keys of the questions to freeze.

    Raises:
        QuestionNotFoundError: If any id does not exist.
    """
    ids = list(dict.fromkeys(question_ids))
    if not ids:
        return

    found = Question.objects.filter(pk__in=ids).count()
    if found != len(ids):
        raise QuestionNotFoundError

    newly_frozen = question_repository.freeze(question_ids=ids)
    if newly_frozen:
        logger.info("questions_frozen count=%s", newly_frozen)


def get_question(
    *, question_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> Question:
    """Fetch one bank question for its owner.

    Raises:
        QuestionNotFoundError: If absent or not the caller's.
    """
    return _require_own(
        question_id=question_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def _require_own(
    *, question_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> Question:
    """Fetch a question the caller manages; "not yours" is the same 404."""
    question = question_selector.get_own_question(
        question_id=question_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if question is None:
        raise QuestionNotFoundError
    return question
