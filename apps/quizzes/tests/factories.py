"""Test data builders for the quiz domain."""

from __future__ import annotations

from itertools import count
from typing import Any

from django.utils import timezone

from apps.quizzes.constants import QuizStatus, QuizVisibility
from apps.quizzes.models import Quiz, QuizQuestion

THAI_QUIZ_TITLE = "แบบทดสอบพื้นฐานการทำขนมปัง"

_sequence = count(1)


def create_quiz(
    *,
    owner: Any,
    title: str | None = None,
    slug: str | None = None,
    status: str = QuizStatus.DRAFT,
    visibility: str = QuizVisibility.PUBLIC,
    **extra: Any,
) -> Quiz:
    """Create a quiz in a given state."""
    index = next(_sequence)
    return Quiz.objects.create(
        owner=owner,
        title=title or f"Quiz {index}",
        slug=slug or f"quiz-{index}",
        description=extra.pop(
            "description", "Check what you learned about home baking."
        ),
        status=status,
        visibility=visibility,
        published_at=extra.pop("published_at", None),
        **extra,
    )


def create_published_quiz(**kwargs: Any) -> Quiz:
    """Create a published, publicly visible quiz."""
    kwargs.setdefault("status", QuizStatus.PUBLISHED)
    kwargs.setdefault("visibility", QuizVisibility.PUBLIC)
    kwargs.setdefault("published_at", timezone.now())
    return create_quiz(**kwargs)


def compose(quiz: Quiz, questions: list[Any], *, points: int = 1) -> None:
    """Assign questions to a quiz directly at the model layer."""
    QuizQuestion.objects.bulk_create(
        QuizQuestion(
            quiz=quiz, question=question, position=position, points=points
        )
        for position, question in enumerate(questions)
    )
