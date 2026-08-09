"""Domain rules for questions and their answer choices.

Pure functions over primitives, used from two places: validating an author's
payload at create/update time, and re-checking **stored** rows when the
quizzes app runs its publish gate (via the public selector API). One rule set,
two moments — the rules must not drift, so they live here once.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apps.questions.constants import (
    MAX_CHOICES_PER_QUESTION,
    MIN_CHOICES_PER_QUESTION,
    TRUE_FALSE_CHOICE_COUNT,
    QuestionType,
)
from apps.questions.exceptions import InvalidQuestionChoicesError


def choice_problems(
    *, question_type: str, choices: Sequence[Mapping[str, object]]
) -> list[str]:
    """Collect every rule violation for a set of answer choices.

    Args:
        question_type: A value of :class:`QuestionType`.
        choices: Mappings with at least ``text`` and ``is_correct``.

    Returns:
        Human-readable problems; empty when the choices are valid.
    """
    problems: list[str] = []
    texts = [str(choice.get("text", "")).strip() for choice in choices]
    correct_count = sum(1 for choice in choices if choice.get("is_correct"))

    if question_type == QuestionType.TRUE_FALSE:
        if len(choices) != TRUE_FALSE_CHOICE_COUNT:
            problems.append(
                f"A true/false question needs exactly {TRUE_FALSE_CHOICE_COUNT} choices."
            )
    elif len(choices) < MIN_CHOICES_PER_QUESTION:
        problems.append(f"Provide at least {MIN_CHOICES_PER_QUESTION} choices.")
    if len(choices) > MAX_CHOICES_PER_QUESTION:
        problems.append(f"Provide at most {MAX_CHOICES_PER_QUESTION} choices.")

    if any(not text for text in texts):
        problems.append("Choices must not be blank.")

    lowered = [text.casefold() for text in texts if text]
    if len(lowered) != len(set(lowered)):
        problems.append("Choices must not repeat.")

    if question_type == QuestionType.MULTIPLE_CHOICE:
        if correct_count < 1:
            problems.append("Mark at least one choice as correct.")
    elif correct_count != 1:
        problems.append("Mark exactly one choice as correct.")

    return problems


def assert_valid_choices(
    *, question_type: str, choices: Sequence[Mapping[str, object]]
) -> None:
    """Validate answer choices or raise with every problem attached.

    Raises:
        InvalidQuestionChoicesError: If any rule is violated.
    """
    problems = choice_problems(question_type=question_type, choices=choices)
    if problems:
        raise InvalidQuestionChoicesError(details={"choices": problems})
