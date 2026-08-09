"""Q&A endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.qa.api.serializers import (
    AcceptAnswerSerializer,
    AnswerCreateSerializer,
    AnswerSerializer,
    ThreadCreateSerializer,
    ThreadSerializer,
    ThreadUpdateSerializer,
)
from apps.qa.selectors import qa_selector
from apps.qa.services import answer_service, thread_service


def _viewer(request: Request) -> tuple[int | None, bool]:
    """Extract the viewer identity pair from a request."""
    if not request.user.is_authenticated:
        return None, False
    return request.user.id, request.user.is_staff


def _int_or_none(raw: str | None) -> int | None:
    """Parse an optional positive-int query parameter, ignoring junk."""
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


class ThreadListCreateView(PaginatedServiceAPIView):
    """Browse visible questions, or ask one."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for creation only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: ThreadSerializer(many=True)}, tags=["qa"])
    def get(self, request: Request) -> Response:
        """Return a page of visible threads, newest first.

        Filters: ``recipe_id``, ``course_id``, ``search``.
        """
        viewer_id, viewer_is_staff = _viewer(request)
        params = request.query_params
        queryset = qa_selector.list_threads(
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
            recipe_id=_int_or_none(params.get("recipe_id")),
            course_id=_int_or_none(params.get("course_id")),
            search=params.get("search"),
        )
        return self.paginated_response(queryset, ThreadSerializer)

    @extend_schema(
        request=ThreadCreateSerializer,
        responses={201: ThreadSerializer},
        tags=["qa"],
    )
    def post(self, request: Request) -> Response:
        """Ask a question about a visible recipe or course."""
        serializer = ThreadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        thread = thread_service.create_thread(
            author_id=request.user.id,
            kind=data["target_type"],
            slug=data["target_slug"],
            data=data,
        )
        return Response(
            ThreadSerializer(thread).data, status=status.HTTP_201_CREATED
        )


class ThreadDetailView(ServiceAPIView):
    """Read, edit, moderate or soft-delete one thread."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for mutation."""
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: ThreadSerializer}, tags=["qa"])
    def get(self, request: Request, thread_id: int) -> Response:
        """Return one thread under the same rule as the list."""
        viewer_id, viewer_is_staff = _viewer(request)
        thread = thread_service.require_visible_thread(
            thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        return Response(ThreadSerializer(thread).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=ThreadUpdateSerializer,
        responses={200: ThreadSerializer},
        tags=["qa"],
    )
    def patch(self, request: Request, thread_id: int) -> Response:
        """Author edits title/body; staff may also change ``status``."""
        serializer = ThreadUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread = thread_service.update_thread(
            thread_id=thread_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(ThreadSerializer(thread).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None}, tags=["qa"])
    def delete(self, request: Request, thread_id: int) -> Response:
        """Soft-delete the thread; history survives, the API forgets it."""
        thread_service.delete_thread(
            thread_id=thread_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ThreadAnswersView(PaginatedServiceAPIView):
    """A thread's answers, or a new answer."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for answering only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: AnswerSerializer(many=True)}, tags=["qa"])
    def get(self, request: Request, thread_id: int) -> Response:
        """Return a page of answers, oldest first (404 on hidden threads)."""
        viewer_id, viewer_is_staff = _viewer(request)
        # The thread gate first: a hidden thread's answers must 404, not
        # serve an empty page.
        thread_service.require_visible_thread(
            thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        queryset = qa_selector.list_answers(
            thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        return self.paginated_response(queryset, AnswerSerializer)

    @extend_schema(
        request=AnswerCreateSerializer,
        responses={201: AnswerSerializer},
        tags=["qa"],
    )
    def post(self, request: Request, thread_id: int) -> Response:
        """Answer an active thread."""
        serializer = AnswerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answer = answer_service.create_answer(
            author_id=request.user.id,
            thread_id=thread_id,
            data=serializer.validated_data,
        )
        return Response(
            AnswerSerializer(answer).data, status=status.HTTP_201_CREATED
        )


class ThreadAcceptView(ServiceAPIView):
    """Mark the accepted answer."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=AcceptAnswerSerializer,
        responses={200: ThreadSerializer},
        tags=["qa"],
    )
    def post(self, request: Request, thread_id: int) -> Response:
        """Thread author (or staff) accepts one of the thread's answers."""
        serializer = AcceptAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread = thread_service.accept_answer(
            thread_id=thread_id,
            answer_id=serializer.validated_data["answer_id"],
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(ThreadSerializer(thread).data, status=status.HTTP_200_OK)


class AnswerDetailView(ServiceAPIView):
    """Edit or delete one answer."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=AnswerCreateSerializer,
        responses={200: AnswerSerializer},
        tags=["qa"],
    )
    def patch(self, request: Request, answer_id: int) -> Response:
        """Author edits their answer's body."""
        serializer = AnswerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answer = answer_service.update_answer(
            answer_id=answer_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(AnswerSerializer(answer).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None}, tags=["qa"])
    def delete(self, request: Request, answer_id: int) -> Response:
        """Hard-delete the caller's answer; an accepted pointer reverts."""
        answer_service.delete_answer(
            answer_id=answer_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
