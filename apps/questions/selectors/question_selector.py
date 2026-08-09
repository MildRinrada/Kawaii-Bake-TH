"""Read-side queries for the question bank.

Also home of the cross-app DTOs. The taker-facing shapes
(:class:`TakerQuestionDTO`, :class:`TakerChoiceDTO`) **structurally lack**
``is_correct`` — leak prevention by construction, the same reasoning as
``PublicProfileDTO`` in the users app: a serializer cannot render a field the
object does not have. The full answer key lives in the sibling module
``answer_key.py``, whose only legitimate caller is quiz scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Prefetch, QuerySet

from apps.questions.constants import QuestionScope
from apps.questions.models import AnswerChoice, Question, QuestionTag
from apps.questions.selectors.question_filters import QuestionListFilters
from apps.questions.validators.question_validator import choice_problems


@dataclass(frozen=True)
class QuestionRef:
    """A bank reference safe to hand across the app boundary.

    What a composing app (quizzes) needs to validate a composition — identity,
    ownership and type — and nothing that could leak an answer.
    """

    id: int
    author_id: int
    question_type: str
    difficulty: str
    frozen_at: datetime | None


@dataclass(frozen=True)
class TakerChoiceDTO:
    """One choice as shown to a quiz taker. There is no ``is_correct`` here."""

    id: int
    text: str
    position: int


@dataclass(frozen=True)
class TakerQuestionDTO:
    """One question as shown to a quiz taker.

    No ``is_correct``, no ``explanation`` — the explanation is revealed only
    after an attempt is submitted, via :func:`list_explanations`.
    """

    id: int
    question_type: str
    text: str
    difficulty: str
    choices: tuple[TakerChoiceDTO, ...]


def list_questions(
    *,
    filters: QuestionListFilters,
    viewer_id: int,
    viewer_is_staff: bool = False,
) -> QuerySet[Question]:
    """Build the bank listing queryset for a viewer.

    The bank is private: the default (and non-staff only) scope is the
    viewer's own questions. A non-staff ``all`` silently narrows to ``mine``
    rather than erroring — an error would confirm more exists.

    Args:
        filters: Parsed, validated query parameters.
        viewer_id: Primary key of the viewer.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A lazy queryset with choices and tags prefetched.
    """
    queryset = Question.objects.prefetch_related("choices", "tags")

    if filters.scope != QuestionScope.ALL or not viewer_is_staff:
        queryset = queryset.filter(author_id=viewer_id)

    if filters.types:
        queryset = queryset.filter(question_type__in=filters.types)
    if filters.difficulty:
        queryset = queryset.filter(difficulty__in=filters.difficulty)
    if filters.tag_slugs:
        queryset = queryset.filter(tags__slug__in=filters.tag_slugs).distinct()
    if filters.search:
        queryset = queryset.filter(text__icontains=filters.search)

    return queryset.order_by("-id")


def get_own_question(
    *, question_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> Question | None:
    """Fetch one question the viewer manages, with choices and tags loaded.

    Args:
        question_id: Primary key of the question.
        viewer_id: Primary key of the viewer.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The question, or ``None`` when absent **or** someone else's — callers
        must not distinguish the two to the client.
    """
    queryset = Question.objects.prefetch_related("choices", "tags")
    if not viewer_is_staff:
        queryset = queryset.filter(author_id=viewer_id)
    return queryset.filter(pk=question_id).first()


def list_refs_by_ids(
    *, ids: list[int], viewer_id: int, viewer_is_staff: bool = False
) -> dict[int, QuestionRef]:
    """Fetch bank references the viewer may compose with.

    Part of the public cross-app API. A question that is absent **or** not the
    viewer's simply does not appear — same fail-closed shape as the visibility
    selectors.

    Args:
        ids: Question primary keys.
        viewer_id: Primary key of the viewer.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        Mapping of question id to :class:`QuestionRef`.
    """
    if not ids:
        return {}
    queryset = Question.objects.filter(pk__in=ids)
    if not viewer_is_staff:
        queryset = queryset.filter(author_id=viewer_id)
    rows = queryset.values(
        "id", "author_id", "question_type", "difficulty", "frozen_at"
    )
    return {row["id"]: QuestionRef(**row) for row in rows}


def list_taker_questions(*, ids: list[int]) -> dict[int, TakerQuestionDTO]:
    """Fetch questions in the shape shown to a quiz taker.

    Part of the public cross-app API. Deliberately **not** viewer-filtered:
    the caller (quizzes) has already decided the viewer may take the quiz, and
    bank ownership does not gate being *asked* a question — only editing it.

    Args:
        ids: Question primary keys.

    Returns:
        Mapping of question id to :class:`TakerQuestionDTO`.
    """
    if not ids:
        return {}
    questions = Question.objects.filter(pk__in=ids).prefetch_related(
        Prefetch("choices", queryset=AnswerChoice.objects.order_by("position", "id"))
    )
    return {
        question.pk: TakerQuestionDTO(
            id=question.pk,
            question_type=question.question_type,
            text=question.text,
            difficulty=question.difficulty,
            choices=tuple(
                TakerChoiceDTO(id=choice.pk, text=choice.text, position=choice.position)
                for choice in question.choices.all()
            ),
        )
        for question in questions
    }


def list_explanations(*, ids: list[int]) -> dict[int, str]:
    """Fetch post-submit explanations.

    Part of the public cross-app API. Callers must only surface these on
    **submitted** attempts — an explanation often paraphrases the answer.

    Args:
        ids: Question primary keys.

    Returns:
        Mapping of question id to its (possibly empty) explanation.
    """
    if not ids:
        return {}
    rows = Question.objects.filter(pk__in=ids).values("id", "explanation")
    return {row["id"]: row["explanation"] for row in rows}


def answer_validation_problems(*, ids: list[int]) -> dict[int, list[str]]:
    """Re-check stored questions against the answer rules.

    Part of the public cross-app API — the quizzes publish gate calls this so
    "every question has valid answers" is checked by the domain that owns the
    rules, against what is actually stored.

    Args:
        ids: Question primary keys.

    Returns:
        Mapping of question id to its problems; ids with no problems are
        absent. Unknown ids are reported as their own problem.
    """
    if not ids:
        return {}
    questions = Question.objects.filter(pk__in=ids).prefetch_related("choices")
    problems: dict[int, list[str]] = {}
    found: set[int] = set()
    for question in questions:
        found.add(question.pk)
        rows = [
            {"text": choice.text, "is_correct": choice.is_correct}
            for choice in question.choices.all()
        ]
        issues = choice_problems(question_type=question.question_type, choices=rows)
        if issues:
            problems[question.pk] = issues
    for missing in set(ids) - found:
        problems[missing] = ["Question no longer exists."]
    return problems


def list_tags() -> QuerySet[QuestionTag]:
    """Return every tag, alphabetically."""
    return QuestionTag.objects.order_by("name")
