"""Write-side database access for quizzes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django.db import IntegrityError, transaction

from apps.quizzes.constants import DEFAULT_QUESTION_POINTS, QUIZ_SLUG_ATTEMPTS
from apps.quizzes.exceptions import QuizSlugGenerationError
from apps.quizzes.models import Quiz, QuizQuestion
from apps.quizzes.utils import quiz_slug_with_suffix


def create_quiz(*, owner_id: int, slug_base: str, **fields: Any) -> Quiz:
    """Create a quiz, resolving slug collisions optimistically.

    Attempt-and-catch in savepoints, exactly as recipes and courses do.

    Args:
        owner_id: Primary key of the owner.
        slug_base: Slug base derived from the title; may be empty.
        **fields: Remaining quiz field values.

    Returns:
        The created quiz.

    Raises:
        QuizSlugGenerationError: If no free slug was found.
    """
    candidate = slug_base or quiz_slug_with_suffix("")

    for _ in range(QUIZ_SLUG_ATTEMPTS):
        try:
            with transaction.atomic():
                return Quiz.objects.create(owner_id=owner_id, slug=candidate, **fields)
        except IntegrityError:
            candidate = quiz_slug_with_suffix(slug_base)

    raise QuizSlugGenerationError


def update_quiz(*, quiz: Quiz, changes: Mapping[str, Any]) -> Quiz:
    """Apply changes to a quiz in a single UPDATE.

    Args:
        quiz: The quiz to update.
        changes: Field name to new value.

    Returns:
        The updated quiz.
    """
    if not changes:
        return quiz

    for field, value in changes.items():
        setattr(quiz, field, value)
    quiz.save(update_fields=[*changes.keys(), "updated_at"])
    return quiz


def set_composition(*, quiz: Quiz, question_ids: Sequence[int]) -> None:
    """Replace a quiz's composition as a collection.

    Safe because nothing references ``QuizQuestion`` rows  attempts snapshot
    what they need at start (see the model docstrings).

    Args:
        quiz: The quiz to recompose.
        question_ids: Bank question ids, in display order.
    """
    quiz.quiz_questions.all().delete()
    QuizQuestion.objects.bulk_create(
        QuizQuestion(
            quiz=quiz,
            question_id=question_id,
            position=index,
            points=DEFAULT_QUESTION_POINTS,
        )
        for index, question_id in enumerate(question_ids)
    )


def delete_quiz(*, quiz: Quiz) -> None:
    """Delete a quiz and its composition rows.

    Raises:
        django.db.models.ProtectedError: If attempts exist  the service maps
            this to the ``quiz_has_attempts`` domain error.
    """
    quiz.delete()
