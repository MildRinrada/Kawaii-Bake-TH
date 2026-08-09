"""Completeness rules that only apply when publishing a quiz.

Pure over primitives: the service gathers what the checks need (its own
composition count, the questions app's verdict on answer validity) and this
module only judges. Deliberately not enforced on every save — a draft must be
saveable while incomplete.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from apps.quizzes.constants import QUIZ_DESCRIPTION_MIN_LENGTH, QUIZ_TITLE_MIN_LENGTH
from apps.quizzes.exceptions import QuizNotPublishableError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.quizzes.models import Quiz


def assert_publishable(
    quiz: Quiz,
    *,
    question_count: int,
    answer_problems: Mapping[int, list[str]],
) -> None:
    """Check that a quiz is complete enough to publish.

    Collects **every** failure so the frontend renders a checklist rather
    than one problem per attempt.

    Args:
        quiz: The quiz about to be published.
        question_count: Size of the quiz's composition.
        answer_problems: The questions app's verdict per question id — the
            domain that owns the answer rules re-checked what is stored.

    Raises:
        QuizNotPublishableError: If any requirement is unmet.
    """
    problems: dict[str, object] = {}

    if len(quiz.title.strip()) < QUIZ_TITLE_MIN_LENGTH:
        problems["title"] = ["Add a longer title."]

    if len(quiz.description.strip()) < QUIZ_DESCRIPTION_MIN_LENGTH:
        problems["description"] = [
            f"Describe the quiz in at least {QUIZ_DESCRIPTION_MIN_LENGTH} characters."
        ]

    if question_count < 1:
        problems["questions"] = ["Add at least one question."]
    elif answer_problems:
        problems["questions"] = {
            str(question_id): issues
            for question_id, issues in sorted(answer_problems.items())
        }

    if problems:
        raise QuizNotPublishableError(details=problems)
