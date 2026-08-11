"""Read-side queries for quiz attempts."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from apps.quizzes.constants import AttemptStatus
from apps.quizzes.models import QuizAttempt, QuizAttemptAnswer


def _answers_prefetch() -> Prefetch:
    """Prefetch answers with their selections, in snapshot order."""
    return Prefetch(
        "answers",
        queryset=QuizAttemptAnswer.objects.order_by("position", "id").prefetch_related(
            "selected_choices"
        ),
    )


def list_attempts(*, user_id: int, quiz_id: int) -> QuerySet[QuizAttempt]:
    """Build the attempt-history queryset for one user on one quiz.

    Own attempts only  a quiz owner's view of student results is future
    instructor analytics, deliberately not this endpoint.

    Args:
        user_id: Primary key of the user.
        quiz_id: Primary key of the quiz.

    Returns:
        A lazy queryset, newest first.
    """
    return QuizAttempt.objects.filter(user_id=user_id, quiz_id=quiz_id).order_by("-id")


def get_attempt(
    *, attempt_id: int, user_id: int, viewer_is_staff: bool = False
) -> QuizAttempt | None:
    """Fetch one attempt with its answer breakdown loaded.

    Args:
        attempt_id: Primary key of the attempt.
        user_id: Primary key of the viewer.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The attempt, or ``None`` when absent **or** someone else's  callers
        must not distinguish the two to the client.
    """
    queryset = QuizAttempt.objects.prefetch_related(_answers_prefetch())
    if not viewer_is_staff:
        queryset = queryset.filter(user_id=user_id)
    return queryset.filter(pk=attempt_id).first()


def get_open_attempt(*, user_id: int, quiz_id: int) -> QuizAttempt | None:
    """Fetch the user's in-progress attempt on a quiz, if any.

    Args:
        user_id: Primary key of the user.
        quiz_id: Primary key of the quiz.

    Returns:
        The open attempt with answers prefetched, or ``None``.
    """
    return (
        QuizAttempt.objects.filter(
            user_id=user_id, quiz_id=quiz_id, status=AttemptStatus.IN_PROGRESS
        )
        .prefetch_related(_answers_prefetch())
        .first()
    )


def completed_quiz_count(*, user_id: int) -> int:
    """How many distinct quizzes the user has submitted at least once.

    Part of the public cross-app API (Phase 9)  the fact count behind
    quiz XP. Distinct quizzes, not attempts: retries are unlimited, so
    counting attempts would make XP farmable.

    Args:
        user_id: Primary key of the user.

    Returns:
        The distinct submitted-quiz count.
    """
    return (
        QuizAttempt.objects.filter(
            user_id=user_id, status=AttemptStatus.SUBMITTED
        )
        .values("quiz_id")
        .distinct()
        .count()
    )


def completed_quiz_ids(*, user_id: int) -> list[int]:
    """The distinct quizzes the user has submitted, as identities.

    Part of the public cross-app API (Phase 13)  the identified sibling
    of :func:`completed_quiz_count`, same anti-farming rule: distinct
    quizzes, not attempts.

    Args:
        user_id: Primary key of the user.

    Returns:
        Quiz ids, ascending for determinism.
    """
    return list(
        QuizAttempt.objects.filter(user_id=user_id, status=AttemptStatus.SUBMITTED)
        .order_by("quiz_id")
        .values_list("quiz_id", flat=True)
        .distinct()
    )


def has_attempted(*, user_id: int, quiz_id: int) -> bool:
    """Whether the user has any attempt (open or submitted) on the quiz."""
    return QuizAttempt.objects.filter(user_id=user_id, quiz_id=quiz_id).exists()
