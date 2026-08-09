"""Lesson endpoints addressed by course slug.

These live under the ``/api/v1/courses/`` URL prefix but belong to the lessons
app — the prefix is a config concern. Each view resolves the course through
courses' public ``get_course_ref`` API, then operates on this app's own rows.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.lessons.api.serializers import (
    LessonCreateSerializer,
    LessonDetailSerializer,
    LessonReorderSerializer,
    LessonSyllabusItemSerializer,
)
from apps.lessons.selectors import lesson_selector
from apps.lessons.services import lesson_service


def _viewer(request: Request) -> tuple[int | None, bool]:
    """Extract the viewer identity pair from a request."""
    if not request.user.is_authenticated:
        return None, False
    return request.user.id, request.user.is_staff


class CourseLessonListView(ServiceAPIView):
    """The syllabus: lesson metadata for everyone who can see the course."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication to add a lesson."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(
        responses={200: LessonSyllabusItemSerializer(many=True)}, tags=["lessons"]
    )
    def get(self, request: Request, slug: str) -> Response:
        """Return the syllabus — lesson metadata only.

        Content and video URLs are behind the lesson detail endpoint's
        enrollment gate, and the viewer's completion state lives at the
        progress app's ``{slug}/progress/`` endpoint — this app knows nothing
        about learner state (ADR 0012). Unpaginated: a course caps at 100
        lessons and the syllabus is rendered as one list.
        """
        viewer_id, viewer_is_staff = _viewer(request)
        course = lesson_service.require_course(
            slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )

        lessons = list(
            lesson_selector.list_for_course(
                course_id=course.id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
            )
        )
        return Response(
            LessonSyllabusItemSerializer(lessons, many=True).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=LessonCreateSerializer,
        responses={201: LessonDetailSerializer},
        tags=["lessons"],
    )
    def post(self, request: Request, slug: str) -> Response:
        """Add a lesson at the end of the course (owner or staff)."""
        serializer = LessonCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lesson = lesson_service.create_lesson(
            course_slug=slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(
            LessonDetailSerializer(
                lesson, context={**self.get_serializer_context(), "recipe_ref": None}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CourseLessonReorderView(ServiceAPIView):
    """Reorder a course's lessons — built for drag-and-drop."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=LessonReorderSerializer,
        responses={200: LessonSyllabusItemSerializer(many=True)},
        tags=["lessons"],
    )
    def post(self, request: Request, slug: str) -> Response:
        """Apply a full ordered id array.

        The payload must contain every lesson of the course exactly once;
        missing, duplicate or foreign ids are reported back as a diff.
        """
        serializer = LessonReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lessons = lesson_service.reorder_lessons(
            course_slug=slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            ordered_ids=serializer.validated_data["lesson_ids"],
        )
        return Response(
            LessonSyllabusItemSerializer(lessons, many=True).data,
            status=status.HTTP_200_OK,
        )
