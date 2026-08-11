"""Progress endpoints, mounted under three prefixes by config."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.progress.api.serializers.progress_serializers import (
    CourseProgressSerializer,
    LessonCompletionSerializer,
    MyCourseProgressSerializer,
)
from apps.progress.services import progress_service


class LessonCompleteView(ServiceAPIView):
    """Mark a lesson complete or clear the flag."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None, responses={200: LessonCompletionSerializer}, tags=["progress"]
    )
    def post(self, request: Request, lesson_id: int) -> Response:
        """Complete the lesson. Idempotent; may complete the course.

        404 when the lesson does not exist for this viewer; 403
        ``enrollment_required`` without an access-granting enrollment 
        including on preview lessons: reading is free, progress is not.
        """
        progress, course_completed = progress_service.complete_lesson(
            user_id=request.user.id, lesson_id=lesson_id
        )
        payload = {
            "lesson_id": lesson_id,
            "completed": progress.completed,
            "completed_at": progress.completed_at,
            "first_completed_at": progress.first_completed_at,
            "course_completed": course_completed,
        }
        return Response(
            LessonCompletionSerializer(payload).data, status=status.HTTP_200_OK
        )

    @extend_schema(responses={200: None}, tags=["progress"])
    def delete(self, request: Request, lesson_id: int) -> Response:
        """Un-complete the lesson; ``first_completed_at`` history survives."""
        progress = progress_service.uncomplete_lesson(
            user_id=request.user.id, lesson_id=lesson_id
        )
        return Response(
            {
                "lesson_id": lesson_id,
                "completed": False,
                "first_completed_at": progress.first_completed_at,
            },
            status=status.HTTP_200_OK,
        )


class CourseProgressView(ServiceAPIView):
    """A student's aggregate progress through one course."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: CourseProgressSerializer}, tags=["progress"])
    def get(self, request: Request, slug: str) -> Response:
        """Return per-lesson and aggregate progress for the caller.

        Also the self-healing half of course auto-completion: computing 100%
        against a still-active enrollment records the completion missed by a
        concurrent-final-lessons race.
        """
        report = progress_service.get_course_progress(
            course_slug=slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            CourseProgressSerializer(report).data, status=status.HTTP_200_OK
        )


class MyProgressView(ServiceAPIView):
    """The caller's progress across every enrolled course."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: MyCourseProgressSerializer(many=True)}, tags=["progress"]
    )
    def get(self, request: Request) -> Response:
        """Return per-course completion summaries.

        Unpaginated by design: the set is bounded by the caller's own
        enrollments and rendered as one dashboard list.
        """
        reports = progress_service.get_my_progress(user_id=request.user.id)
        return Response(
            {"courses": MyCourseProgressSerializer(reports, many=True).data},
            status=status.HTTP_200_OK,
        )
