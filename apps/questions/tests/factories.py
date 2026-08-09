"""Test data builders for the question bank.

Thai fixtures from the first commit, as in every phase — text handling must
prove itself on Thai, not just ASCII.
"""

from __future__ import annotations

from itertools import count
from typing import Any

from apps.questions.constants import QuestionType
from apps.questions.models import AnswerChoice, Question

THAI_QUESTION_TEXT = "แป้งชนิดใดเหมาะกับการทำครัวซองมากที่สุด?"

_sequence = count(1)


def create_question(
    *,
    author: Any,
    question_type: str = QuestionType.SINGLE_CHOICE,
    text: str | None = None,
    choices: list[tuple[str, bool]] | None = None,
    **extra: Any,
) -> Question:
    """Create a question with choices directly at the model layer.

    Args:
        author: The owning user.
        question_type: A value of :class:`QuestionType`.
        text: Question text; a default is generated when omitted.
        choices: ``(text, is_correct)`` pairs; a valid default per type when
            omitted.
        **extra: Remaining question field values.

    Returns:
        The created question.
    """
    index = next(_sequence)
    question = Question.objects.create(
        author=author,
        question_type=question_type,
        text=text or f"Question {index}?",
        **extra,
    )
    if choices is None:
        if question_type == QuestionType.TRUE_FALSE:
            choices = [("True", True), ("False", False)]
        elif question_type == QuestionType.MULTIPLE_CHOICE:
            choices = [("A", True), ("B", True), ("C", False)]
        else:
            choices = [("A", True), ("B", False), ("C", False)]
    AnswerChoice.objects.bulk_create(
        AnswerChoice(
            question=question, text=text_, is_correct=correct, position=position
        )
        for position, (text_, correct) in enumerate(choices)
    )
    return question


def correct_choice_ids(question: Question) -> list[int]:
    """Return the ids of the question's correct choices."""
    return list(
        question.choices.filter(is_correct=True).values_list("id", flat=True)
    )


def wrong_choice_id(question: Question) -> int:
    """Return the id of one incorrect choice."""
    return question.choices.filter(is_correct=False).values_list("id", flat=True)[0]
