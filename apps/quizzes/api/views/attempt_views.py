"""Attempt endpoints: start, submit, history, review, abandon."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.quizzes.api.serializers import (
    AttemptAnswerSerializer,
    AttemptSummarySerializer,
    QuizSubmitSerializer,
)
from apps.quizzes.models import QuizAttempt
from apps.quizzes.selectors import attempt_selector
from apps.quizzes.services import attempt_service


def _attempt_payload(
    attempt: QuizAttempt, *, context: dict[str, Any]
) -> dict[str, Any]:
    """Build the attempt envelope: summary plus the per-question breakdown."""
    questions, explanations = attempt_service.review_context(attempt=attempt)
    answer_context = {
        **context,
        "questions": questions,
        "explanations": explanations,
    }
    return {
        **AttemptSummarySerializer(attempt, context=context).data,
        "answers": AttemptAnswerSerializer(
            attempt.answers.all(), many=True, context=answer_context
        ).data,
    }


class QuizStartView(ServiceAPIView):
    """Start (or resume) an attempt."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={201: None, 200: None}, tags=["quizzes"])
    def post(self, request: Request, slug: str) -> Response:
        """Start an attempt. Idempotent: 201 on creation, 200 when resuming.

        The response carries the questions in the taker-safe shape — this,
        not the quiz detail, is the moment a taker receives the questions.
        """
        attempt, created = attempt_service.start_attempt(
            user_id=request.user.id, slug=slug
        )
        attempt = attempt_service.get_attempt(
            user_id=request.user.id, slug=slug, attempt_id=attempt.pk
        )
        return Response(
            _attempt_payload(attempt, context=self.get_serializer_context()),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class QuizSubmitView(ServiceAPIView):
    """Submit the open attempt for grading."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=QuizSubmitSerializer, responses={200: None}, tags=["quizzes"])
    def post(self, request: Request, slug: str) -> Response:
        """Grade and close the caller's open attempt.

        Omitted questions are graded as skipped (incorrect). A second submit
        is 409 ``attempt_already_submitted`` — an attempt is graded once.
        """
        serializer = QuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        attempt, _results = attempt_service.submit_attempt(
            user_id=request.user.id,
            slug=slug,
            answers=serializer.validated_data["answers"],
        )
        return Response(
            _attempt_payload(attempt, context=self.get_serializer_context()),
            status=status.HTTP_200_OK,
        )


class AttemptListView(PaginatedServiceAPIView):
    """The caller's own attempt history on one quiz."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: AttemptSummarySerializer(many=True)}, tags=["quizzes"]
    )
    def get(self, request: Request, slug: str) -> Response:
        """Return a page of the caller's attempts, newest first."""
        quiz = attempt_service.require_visible_quiz(
            user_id=request.user.id,
            slug=slug,
            viewer_is_staff=request.user.is_staff,
        )
        queryset = attempt_selector.list_attempts(
            user_id=request.user.id, quiz_id=quiz.id
        )
        return self.paginated_response(queryset, AttemptSummarySerializer)


class AttemptDetailView(ServiceAPIView):
    """One attempt's full breakdown, or abandon an open attempt."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: None}, tags=["quizzes"])
    def get(self, request: Request, slug: str, attempt_id: int) -> Response:
        """Return the attempt with its per-question review."""
        attempt = attempt_service.get_attempt(
            user_id=request.user.id,
            slug=slug,
            attempt_id=attempt_id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            _attempt_payload(attempt, context=self.get_serializer_context()),
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["quizzes"])
    def delete(self, request: Request, slug: str, attempt_id: int) -> Response:
        """Abandon the caller's open attempt; submitted history is permanent."""
        attempt_service.abandon_attempt(
            user_id=request.user.id, slug=slug, attempt_id=attempt_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
