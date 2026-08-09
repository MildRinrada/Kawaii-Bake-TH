"""The answer key — the one read path that exposes correctness.

**The only legitimate caller of this module is quiz scoring**
(``apps.quizzes.services.scoring_service`` via ``attempt_service``). It must
never be imported from any ``api/`` package, any serializer, or any view.
Keeping the key in its own screaming-name module makes that auditable with a
single grep; an import-linter contract should pin it down when adopted.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch

from apps.questions.models import AnswerChoice, Question


@dataclass(frozen=True)
class AnswerKey:
    """Everything needed to grade one question, and nothing more."""

    question_id: int
    question_type: str
    correct_choice_ids: frozenset[int]
    all_choice_ids: frozenset[int]


def get_answer_keys(*, ids: list[int]) -> dict[int, AnswerKey]:
    """Fetch the grading key for a set of questions.

    Args:
        ids: Question primary keys.

    Returns:
        Mapping of question id to its :class:`AnswerKey`.
    """
    if not ids:
        return {}
    questions = Question.objects.filter(pk__in=ids).prefetch_related(
        Prefetch("choices", queryset=AnswerChoice.objects.only("id", "is_correct", "question_id"))
    )
    keys: dict[int, AnswerKey] = {}
    for question in questions:
        choices = list(question.choices.all())
        keys[question.pk] = AnswerKey(
            question_id=question.pk,
            question_type=question.question_type,
            correct_choice_ids=frozenset(c.pk for c in choices if c.is_correct),
            all_choice_ids=frozenset(c.pk for c in choices),
        )
    return keys
