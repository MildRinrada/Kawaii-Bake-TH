"""Quiz list, create, detail, update and delete endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.quizzes.api.serializers import (
    QuizCreateSerializer,
    QuizDetailSerializer,
    QuizListItemSerializer,
    QuizListQuerySerializer,
    QuizUpdateSerializer,
)
from apps.quizzes.constants import QuizScope
from apps.quizzes.selectors import quiz_selector
from apps.quizzes.selectors.quiz_filters import QuizListFilters
from apps.quizzes.services import quiz_service


def _viewer(request: Request) -> tuple[int | None, bool]:
    """Extract the viewer identity pair from a request."""
    if not request.user.is_authenticated:
        return None, False
    return request.user.id, request.user.is_staff


class QuizListCreateView(PaginatedServiceAPIView):
    """List visible quizzes, or create a new one."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for creation only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(
        parameters=[QuizListQuerySerializer],
        responses={200: QuizListItemSerializer(many=True)},
        tags=["quizzes"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of quizzes visible to the caller."""
        query = QuizListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        validated = query.validated_data

        filters = QuizListFilters(
            owner_username=validated.get("owner", "") or "",
            ordering=validated.get("ordering", QuizListFilters.ordering),
            scope=validated.get("scope", QuizScope.PUBLIC),
        )
        if filters.scope == QuizScope.MINE and not request.user.is_authenticated:
            raise NotAuthenticated

        viewer_id, viewer_is_staff = _viewer(request)
        queryset = quiz_selector.list_quizzes(
            filters=filters, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        return self.paginated_response(queryset, QuizListItemSerializer)

    @extend_schema(
        request=QuizCreateSerializer,
        responses={201: QuizDetailSerializer},
        tags=["quizzes"],
    )
    def post(self, request: Request) -> Response:
        """Create a quiz as a draft."""
        serializer = QuizCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quiz = quiz_service.create_quiz(
            owner_id=request.user.id, data=serializer.validated_data
        )
        return self._detail_response(request, quiz.slug, status.HTTP_201_CREATED)

    def _detail_response(
        self, request: Request, slug: str, status_code: int
    ) -> Response:
        """Serialize the full detail payload for a just-written quiz."""
        viewer_id, viewer_is_staff = _viewer(request)
        quiz, questions, _points = quiz_service.get_quiz_with_questions(
            slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        context = {**self.get_serializer_context(), "questions": questions}
        return Response(
            QuizDetailSerializer(quiz, context=context).data, status=status_code
        )


class QuizDetailView(ServiceAPIView):
    """Read, update or delete one quiz."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for writes."""
        if self.request.method in {"PATCH", "PUT", "DELETE"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: QuizDetailSerializer}, tags=["quizzes"])
    def get(self, request: Request, slug: str) -> Response:
        """Return one quiz with its questions in the taker-safe shape.

        One shape for every viewer; hidden and absent are the same 404.
        """
        viewer_id, viewer_is_staff = _viewer(request)
        quiz, questions, _points = quiz_service.get_quiz_with_questions(
            slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        context = {**self.get_serializer_context(), "questions": questions}
        return Response(
            QuizDetailSerializer(quiz, context=context).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=QuizUpdateSerializer,
        responses={200: QuizDetailSerializer},
        tags=["quizzes"],
    )
    def patch(self, request: Request, slug: str) -> Response:
        """Partially update a quiz; ``question_ids`` replaces the composition."""
        serializer = QuizUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quiz = quiz_service.update_quiz(
            slug=slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        _quiz, questions, _points = quiz_service.get_quiz_with_questions(
            slug=quiz.slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        context = {**self.get_serializer_context(), "questions": questions}
        return Response(
            QuizDetailSerializer(quiz, context=context).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["quizzes"])
    def delete(self, request: Request, slug: str) -> Response:
        """Delete a quiz; 409 ``quiz_has_attempts`` once history exists."""
        quiz_service.delete_quiz(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
