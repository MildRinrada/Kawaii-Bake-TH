"""Course lifecycle and enrollment endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.courses.api.serializers import CourseDetailSerializer
from apps.courses.services import course_service, enrollment_service, publish_service


class _TransitionView(ServiceAPIView):
    """Shared plumbing for the three lifecycle transitions."""

    permission_classes = (IsAuthenticated,)
    transition = ""

    def post(self, request: Request, slug: str) -> Response:
        """Apply the transition and return the updated course."""
        action = getattr(publish_service, self.transition)
        action(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )
        course = course_service.get_course(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )
        return Response(
            CourseDetailSerializer(course, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class CoursePublishView(_TransitionView):
    """Publish a course."""

    transition = "publish"

    @extend_schema(request=None, responses={200: CourseDetailSerializer}, tags=["courses"])
    def post(self, request: Request, slug: str) -> Response:
        """Publish; 400 ``course_not_publishable`` lists every unmet requirement."""
        return super().post(request, slug)


class CourseUnpublishView(_TransitionView):
    """Return a course to draft  hides it even from enrolled students."""

    transition = "unpublish"

    @extend_schema(request=None, responses={200: CourseDetailSerializer}, tags=["courses"])
    def post(self, request: Request, slug: str) -> Response:
        """Unpublish the course."""
        return super().post(request, slug)


class CourseArchiveView(_TransitionView):
    """Archive a course  enrolled students keep read access."""

    transition = "archive"

    @extend_schema(request=None, responses={200: CourseDetailSerializer}, tags=["courses"])
    def post(self, request: Request, slug: str) -> Response:
        """Archive the course."""
        return super().post(request, slug)


class EnrollView(ServiceAPIView):
    """Enroll in a course."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={201: None, 200: None}, tags=["courses"])
    def post(self, request: Request, slug: str) -> Response:
        """Enroll the caller. Idempotent: 201 on first enrollment, 200 after."""
        enrollment, created = enrollment_service.enroll(
            user_id=request.user.id, slug=slug
        )
        return Response(
            {"status": enrollment.status},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UnenrollView(ServiceAPIView):
    """Drop a course."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={204: None}, tags=["courses"])
    def delete(self, request: Request, slug: str) -> Response:
        """Drop the course. Soft: enrollment history and progress survive."""
        enrollment_service.unenroll(user_id=request.user.id, slug=slug)
        return Response(status=status.HTTP_204_NO_CONTENT)
