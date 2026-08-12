"""Read-side queries for threads and answers."""

from __future__ import annotations

from typing import Any

from django.db.models import Count, F, Max, Q, QuerySet

from apps.qa.constants import ThreadOrdering, ThreadTargetKind
from apps.qa.models import QuestionAnswer, QuestionThread
from apps.qa.selectors.qa_visibility import visible_q

# Every ordering ends in the same tiebreakers, so a page boundary can
# never show one row twice or skip one. `nulls_last` is explicit because
# SQLite and PostgreSQL disagree about where NULL sorts, and a thread
# with no answers must land at the bottom of "recently answered" on both.
_ORDER_BY: dict[str, tuple[Any, ...]] = {
    ThreadOrdering.LATEST: ("-created_at", "-id"),
    ThreadOrdering.ACTIVE: (
        F("last_answer_at").desc(nulls_last=True),
        "-created_at",
        "-id",
    ),
    ThreadOrdering.POPULAR: ("-view_count", "-created_at", "-id"),
}


def _thread_queryset() -> QuerySet[QuestionThread]:
    """The shape every thread read shares.

    The three numbers a reader picks a thread by  answers, readers, and
    when it was last answered  are annotated, never stored (the model
    docstring's promise). ``distinct=True`` on both counts because the
    two aggregates share one query: without it each would multiply by
    the other's row count.
    """
    return (
        QuestionThread.objects.select_related(
            "author", "recipe", "course", "accepted_answer", "accepted_answer__author"
        )
        .annotate(
            answer_count=Count("answers", distinct=True),
            view_count=Count("views", distinct=True),
            last_answer_at=Max("answers__created_at"),
        )
        # Aggregation drops the model's implicit ordering, so every read
        # states its own.
        .order_by("-created_at", "-id")
    )


def list_threads(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    recipe_id: int | None = None,
    course_id: int | None = None,
    search: str | None = None,
    resolved: bool | None = None,
    target: str | None = None,
    category: str | None = None,
    ordering: str = ThreadOrdering.LATEST,
) -> QuerySet[QuestionThread]:
    """Visible threads under the requested sort; filters only narrow.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        recipe_id: Restrict to one recipe's threads.
        course_id: Restrict to one course's threads.
        search: Case-insensitive substring over title and body.
        resolved: ``True`` for threads with an accepted answer, ``False``
            for those still waiting, ``None`` for both.
        target: ``"recipe"`` or ``"course"`` to keep only threads asking
            about that kind of content.
        category: Slug of a recipe category the target belongs to.
        ordering: A value of :class:`ThreadOrdering`; anything else falls
            back to newest-first rather than erroring, because a sort is
            a preference, not a contract.

    Returns:
        A lazy queryset.
    """
    queryset = _thread_queryset().filter(
        visible_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff)
    )
    if recipe_id is not None:
        queryset = queryset.filter(recipe_id=recipe_id)
    if course_id is not None:
        queryset = queryset.filter(course_id=course_id)
    if search:
        term = search.strip()
        if term:
            queryset = queryset.filter(
                Q(title__icontains=term) | Q(body__icontains=term)
            )
    if resolved is True:
        queryset = queryset.filter(accepted_answer__isnull=False)
    elif resolved is False:
        queryset = queryset.filter(accepted_answer__isnull=True)
    if target == ThreadTargetKind.RECIPE:
        queryset = queryset.filter(recipe__isnull=False)
    elif target == ThreadTargetKind.COURSE:
        queryset = queryset.filter(course__isnull=False)
    if category:
        # A thread inherits the category of whichever target it has, so
        # one filter covers both kinds.
        queryset = queryset.filter(
            Q(recipe__categories__slug=category)
            | Q(course__categories__slug=category)
        ).distinct()
    return queryset.order_by(
        *_ORDER_BY.get(ordering, _ORDER_BY[ThreadOrdering.LATEST])
    )


def get_thread(
    *, thread_id: int, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> QuestionThread | None:
    """Fetch one thread under the same rule as the list.

    Args:
        thread_id: Primary key of the thread.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The thread, or ``None`` when absent, deleted, or hidden from view.
    """
    return (
        _thread_queryset()
        .filter(visible_q(viewer_id=viewer_id, viewer_is_staff=viewer_is_staff))
        .filter(pk=thread_id)
        .first()
    )


def list_answers(
    *, thread_id: int, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> QuerySet[QuestionAnswer]:
    """A thread's answers, oldest first, under the thread's visibility.

    The join through ``visible_q(prefix="thread__")`` means answers of a
    hidden or deleted thread simply do not exist here  the same rule as
    the thread itself, one implementation.

    Args:
        thread_id: Primary key of the thread.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A lazy queryset with authors preloaded.
    """
    return (
        QuestionAnswer.objects.filter(
            visible_q(
                viewer_id=viewer_id,
                viewer_is_staff=viewer_is_staff,
                prefix="thread__",
            )
        )
        .filter(thread_id=thread_id)
        .select_related("author")
    )


def get_answer(
    *, answer_id: int, viewer_id: int | None = None, viewer_is_staff: bool = False
) -> QuestionAnswer | None:
    """Fetch one answer under its thread's visibility.

    Args:
        answer_id: Primary key of the answer.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The answer with its thread loaded, or ``None``.
    """
    return (
        QuestionAnswer.objects.filter(
            visible_q(
                viewer_id=viewer_id,
                viewer_is_staff=viewer_is_staff,
                prefix="thread__",
            )
        )
        .filter(pk=answer_id)
        .select_related("thread", "author")
        .first()
    )
