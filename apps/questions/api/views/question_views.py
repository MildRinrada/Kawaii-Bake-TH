"""Question bank endpoints  a private, authenticated authoring surface."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.questions.api.serializers import (
    OwnerQuestionSerializer,
    QuestionCreateSerializer,
    QuestionListQuerySerializer,
    QuestionTagSerializer,
    QuestionUpdateSerializer,
)
from apps.questions.constants import QuestionScope
from apps.questions.selectors import question_selector
from apps.questions.selectors.question_filters import QuestionListFilters
from apps.questions.services import question_service


class QuestionListCreateView(PaginatedServiceAPIView):
    """List the caller's question bank, or add to it."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[QuestionListQuerySerializer],
        responses={200: OwnerQuestionSerializer(many=True)},
        tags=["questions"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of the caller's questions."""
        query = QuestionListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        validated = query.validated_data

        filters = QuestionListFilters(
            types=tuple(validated.get("type", ()) or ()),
            difficulty=tuple(validated.get("difficulty", ()) or ()),
            tag_slugs=tuple(validated.get("tag", ()) or ()),
            search=validated.get("search", "") or "",
            scope=validated.get("scope", QuestionScope.MINE),
        )
        queryset = question_selector.list_questions(
            filters=filters,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return self.paginated_response(queryset, OwnerQuestionSerializer)

    @extend_schema(
        request=QuestionCreateSerializer,
        responses={201: OwnerQuestionSerializer},
        tags=["questions"],
    )
    def post(self, request: Request) -> Response:
        """Create a question; 400 ``invalid_choices`` lists every problem."""
        serializer = QuestionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question = question_service.create_question(
            author_id=request.user.id, data=serializer.validated_data
        )
        return Response(
            OwnerQuestionSerializer(
                question, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )


class QuestionDetailView(ServiceAPIView):
    """Read, update or delete one bank question."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: OwnerQuestionSerializer}, tags=["questions"])
    def get(self, request: Request, question_id: int) -> Response:
        """Return one question; someone else's id is the same 404 as absent."""
        question = question_service.get_question(
            question_id=question_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            OwnerQuestionSerializer(
                question, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=QuestionUpdateSerializer,
        responses={200: OwnerQuestionSerializer},
        tags=["questions"],
    )
    def patch(self, request: Request, question_id: int) -> Response:
        """Partially update; content changes on a frozen question are 409."""
        serializer = QuestionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question = question_service.update_question(
            question_id=question_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(
            OwnerQuestionSerializer(
                question, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["questions"])
    def delete(self, request: Request, question_id: int) -> Response:
        """Delete; 409 when frozen (``question_frozen``) or in a quiz (``question_in_use``)."""
        question_service.delete_question(
            question_id=question_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuestionTagListView(ServiceAPIView):
    """List every tag in use."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: QuestionTagSerializer(many=True)}, tags=["questions"])
    def get(self, request: Request) -> Response:
        """Return all tags, alphabetically."""
        tags = question_selector.list_tags()
        return Response(
            QuestionTagSerializer(tags, many=True).data, status=status.HTTP_200_OK
        )
