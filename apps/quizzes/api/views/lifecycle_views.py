"""Quiz lifecycle transition endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.quizzes.api.serializers import QuizListItemSerializer
from apps.quizzes.selectors import quiz_selector
from apps.quizzes.services import publish_service


class _TransitionView(ServiceAPIView):
    """Shared plumbing for the three lifecycle transitions."""

    permission_classes = (IsAuthenticated,)
    transition = ""

    def post(self, request: Request, slug: str) -> Response:
        """Apply the transition and return the updated quiz summary."""
        action = getattr(publish_service, self.transition)
        quiz = action(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )
        refreshed = quiz_selector.get_quiz_detail(
            slug=quiz.slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            QuizListItemSerializer(
                refreshed, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )


class QuizPublishView(_TransitionView):
    """Publish a quiz."""

    transition = "publish"

    @extend_schema(request=None, responses={200: QuizListItemSerializer}, tags=["quizzes"])
    def post(self, request: Request, slug: str) -> Response:
        """Publish; 400 ``quiz_not_publishable`` lists every unmet requirement."""
        return super().post(request, slug)


class QuizUnpublishView(_TransitionView):
    """Return a quiz to draft  the hard kill switch."""

    transition = "unpublish"

    @extend_schema(request=None, responses={200: QuizListItemSerializer}, tags=["quizzes"])
    def post(self, request: Request, slug: str) -> Response:
        """Unpublish the quiz; open attempts may still be submitted."""
        return super().post(request, slug)


class QuizArchiveView(_TransitionView):
    """Archive a quiz  attempt history stays readable to its owners."""

    transition = "archive"

    @extend_schema(request=None, responses={200: QuizListItemSerializer}, tags=["quizzes"])
    def post(self, request: Request, slug: str) -> Response:
        """Archive the quiz; no new attempts, history survives."""
        return super().post(request, slug)
