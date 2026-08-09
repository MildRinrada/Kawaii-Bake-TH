"""Read-side queries for quizzes.

Also home of :class:`QuizRef` — the frozen reference the ``lessons`` app uses
for its optional per-lesson quiz link. Part of the public cross-app API.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, QuerySet

from apps.quizzes.constants import QUIZ_ORDERING_MAP
from apps.quizzes.models import Quiz, QuizQuestion
from apps.quizzes.selectors.quiz_filters import QuizListFilters
from apps.quizzes.selectors.quiz_visibility import visible_detail_q, visible_in_list_q


@dataclass(frozen=True)
class QuizRef:
    """A quiz reference safe to hand across the app boundary."""

    id: int
    slug: str
    title: str
    owner_id: int
    status: str
    visibility: str
    pass_percent: int
    question_count: int


@dataclass(frozen=True)
class CompositionRow:
    """One placement in a quiz's composition — what a snapshot copies."""

    question_id: int
    position: int
    points: int


def _base_list_queryset() -> QuerySet[Quiz]:
    """Return the queryset shape shared by every quiz listing."""
    return (
        Quiz.objects.select_related("owner", "owner__profile")
        .annotate(question_count=Count("quiz_questions"))
        .defer("description")
    )


def list_quizzes(
    *,
    filters: QuizListFilters,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
) -> QuerySet[Quiz]:
    """Build the quiz listing queryset for a viewer.

    Args:
        filters: Parsed, validated query parameters.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A lazy queryset of visible quizzes.
    """
    queryset = _base_list_queryset().filter(
        visible_in_list_q(
            viewer_id=viewer_id, viewer_is_staff=viewer_is_staff, scope=filters.scope
        )
    )
    if filters.owner_username:
        queryset = queryset.filter(owner__username__iexact=filters.owner_username)
    return queryset.order_by(*QUIZ_ORDERING_MAP[filters.ordering])


def get_quiz_detail(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> Quiz | None:
    """Fetch one quiz with everything the detail payload needs.

    Args:
        slug: The quiz slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The quiz, or ``None`` when absent or hidden — callers must not
        distinguish the two to the client.
    """
    return (
        Quiz.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .select_related("owner", "owner__profile")
        .annotate(question_count=Count("quiz_questions", distinct=True))
        .first()
    )


def get_editable_quiz(
    *, slug: str, viewer_id: int, viewer_is_staff: bool = False
) -> Quiz | None:
    """Fetch a quiz for a write operation.

    Write permission is decided by ``permissions/``; this only ensures the
    caller can even name the quiz.
    """
    return (
        Quiz.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .first()
    )


def get_quiz_ref(
    *, slug: str, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> QuizRef | None:
    """Fetch a quiz reference for another app or the attempt flow.

    Part of the public cross-app API. Returns ``None`` when the quiz is absent
    **or** hidden from this viewer; the caller raises its own domain error.

    Args:
        slug: The quiz slug.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A :class:`QuizRef`, or ``None``.
    """
    row = (
        Quiz.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(slug__iexact=slug.strip())
        .annotate(question_total=Count("quiz_questions", distinct=True))
        .values(
            "id",
            "slug",
            "title",
            "owner_id",
            "status",
            "visibility",
            "pass_percent",
            "question_total",
        )
        .first()
    )
    if row is None:
        return None
    row["question_count"] = row.pop("question_total")
    return QuizRef(**row)


def list_refs_by_ids(
    *, ids: list[int], viewer_id: int | None = None, viewer_is_staff: bool = False
) -> dict[int, QuizRef]:
    """Fetch visible quiz references by id.

    Part of the public cross-app API — the lessons app validates and embeds
    its quiz links through this, so a quiz that later goes private degrades to
    absent rather than leaking.

    Args:
        ids: Quiz primary keys.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        Mapping of quiz id to :class:`QuizRef`.
    """
    if not ids:
        return {}
    rows = (
        Quiz.objects.filter(
            visible_detail_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
        )
        .filter(pk__in=ids)
        .annotate(question_total=Count("quiz_questions", distinct=True))
        .values(
            "id",
            "slug",
            "title",
            "owner_id",
            "status",
            "visibility",
            "pass_percent",
            "question_total",
        )
        .distinct()
    )
    refs: dict[int, QuizRef] = {}
    for row in rows:
        row["question_count"] = row.pop("question_total")
        refs[row["id"]] = QuizRef(**row)
    return refs


def list_composition(*, quiz_id: int) -> list[CompositionRow]:
    """Fetch a quiz's composition in display order.

    Args:
        quiz_id: Primary key of the quiz.

    Returns:
        Ordered composition rows.
    """
    rows = (
        QuizQuestion.objects.filter(quiz_id=quiz_id)
        .order_by("position", "id")
        .values("question_id", "position", "points")
    )
    return [CompositionRow(**row) for row in rows]


def slug_exists(*, slug: str, exclude_pk: int | None = None) -> bool:
    """Whether a quiz slug is already taken.

    Args:
        slug: The candidate slug.
        exclude_pk: A quiz to ignore, for update validation.

    Returns:
        ``True`` if the slug is in use.
    """
    queryset = Quiz.objects.filter(slug__iexact=slug.strip())
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()
