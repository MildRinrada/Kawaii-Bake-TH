"""Read-side queries for threads and answers."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.qa.models import QuestionAnswer, QuestionThread
from apps.qa.selectors.qa_visibility import visible_q


def _thread_queryset() -> QuerySet[QuestionThread]:
    """The shape every thread read shares."""
    return QuestionThread.objects.select_related(
        "author", "recipe", "course", "accepted_answer", "accepted_answer__author"
    )


def list_threads(
    *,
    viewer_id: int | None = None,
    viewer_is_staff: bool = False,
    recipe_id: int | None = None,
    course_id: int | None = None,
    search: str | None = None,
) -> QuerySet[QuestionThread]:
    """Visible threads, newest first; filters only narrow.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.
        recipe_id: Restrict to one recipe's threads.
        course_id: Restrict to one course's threads.
        search: Case-insensitive substring over title and body.

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
    return queryset


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
    hidden or deleted thread simply do not exist here — the same rule as
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
