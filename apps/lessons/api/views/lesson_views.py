"""Standalone lesson endpoints (mounted at ``/api/v1/lessons/``)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.lessons.api.serializers import (
    LessonDetailSerializer,
    LessonUpdateSerializer,
)
from apps.lessons.exceptions import EnrollmentRequiredError
from apps.lessons.models import Lesson
from apps.lessons.services import lesson_service
from apps.quizzes.selectors import quiz_selector
from apps.recipes.api.serializers import RecipeListItemSerializer
from apps.recipes.selectors import recipe_selector


def _viewer(request: Request) -> tuple[int | None, bool]:
    """Extract the viewer identity pair from a request."""
    if not request.user.is_authenticated:
        return None, False
    return request.user.id, request.user.is_staff


def _recipe_ref(request: Request, lesson: Lesson) -> dict[str, Any] | None:
    """Fetch the linked recipe redacted for this viewer, or ``None``.

    Uses the viewer-aware ``list_by_ids``, so a recipe that has gone private
    since linking degrades to ``None`` rather than leaking.
    """
    if lesson.recipe_id is None:
        return None

    viewer_id, viewer_is_staff = _viewer(request)
    recipe = (
        recipe_selector.list_by_ids(
            ids=[lesson.recipe_id],
            viewer_id=viewer_id,
            viewer_is_staff=viewer_is_staff,
        )
        .first()
    )
    if recipe is None:
        return None
    return RecipeListItemSerializer(recipe, context={"request": request}).data


def _quiz_ref(request: Request, lesson: Lesson) -> dict[str, Any] | None:
    """Fetch the linked quiz reference redacted for this viewer, or ``None``.

    Uses the viewer-aware ``list_refs_by_ids``, so a quiz that has gone
    private or back to draft since linking degrades to ``None`` rather than
    leaking. Only reference fields are embedded  questions live behind the
    quiz's own endpoints.
    """
    if lesson.quiz_id is None:
        return None

    viewer_id, viewer_is_staff = _viewer(request)
    ref = quiz_selector.list_refs_by_ids(
        ids=[lesson.quiz_id], viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    ).get(lesson.quiz_id)
    if ref is None:
        return None
    return {
        "id": ref.id,
        "slug": ref.slug,
        "title": ref.title,
        "pass_percent": ref.pass_percent,
        "question_count": ref.question_count,
    }


class LessonDetailView(ServiceAPIView):
    """Read, update or delete one lesson."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for writes."""
        if self.request.method in {"PATCH", "PUT", "DELETE"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: LessonDetailSerializer}, tags=["lessons"])
    def get(self, request: Request, lesson_id: int) -> Response:
        """Return full lesson content, enforcing the two-layer gate.

        404 when the lesson does not exist for this viewer; 401 when an
        anonymous viewer hits the enrollment gate (the frontend redirects to
        login); 403 ``enrollment_required`` when a signed-in viewer is simply
        not enrolled (the frontend renders the Enroll CTA).
        """
        viewer_id, viewer_is_staff = _viewer(request)
        try:
            lesson = lesson_service.get_lesson_content(
                lesson_id=lesson_id,
                viewer_id=viewer_id,
                viewer_is_staff=viewer_is_staff,
            )
        except EnrollmentRequiredError:
            if viewer_id is None:
                raise NotAuthenticated from None
            raise

        context = {
            **self.get_serializer_context(),
            "recipe_ref": _recipe_ref(request, lesson),
            "quiz_ref": _quiz_ref(request, lesson),
        }
        return Response(
            LessonDetailSerializer(lesson, context=context).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=LessonUpdateSerializer,
        responses={200: LessonDetailSerializer},
        tags=["lessons"],
    )
    def patch(self, request: Request, lesson_id: int) -> Response:
        """Partially update a lesson (owner or staff)."""
        serializer = LessonUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lesson = lesson_service.update_lesson(
            lesson_id=lesson_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        context = {
            **self.get_serializer_context(),
            "recipe_ref": _recipe_ref(request, lesson),
            "quiz_ref": _quiz_ref(request, lesson),
        }
        return Response(
            LessonDetailSerializer(lesson, context=context).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["lessons"])
    def delete(self, request: Request, lesson_id: int) -> Response:
        """Delete a lesson; the course's remaining lessons are renumbered."""
        lesson_service.delete_lesson(
            lesson_id=lesson_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
