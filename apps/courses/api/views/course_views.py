"""Course list, create, detail, update and delete endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.courses.api.serializers import (
    CourseCreateSerializer,
    CourseDetailSerializer,
    CourseListItemSerializer,
    CourseListQuerySerializer,
    CourseUpdateSerializer,
)
from apps.courses.constants import CourseScope
from apps.courses.selectors import course_selector
from apps.courses.selectors.course_filters import CourseListFilters
from apps.courses.services import course_service


def _viewer(request: Request) -> tuple[int | None, bool]:
    """Extract the viewer identity pair from a request."""
    if not request.user.is_authenticated:
        return None, False
    return request.user.id, request.user.is_staff


class CourseListCreateView(PaginatedServiceAPIView):
    """List visible courses, or create a new one."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for creation only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(
        parameters=[CourseListQuerySerializer],
        responses={200: CourseListItemSerializer(many=True)},
        tags=["courses"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of courses visible to the caller."""
        query = CourseListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        validated = query.validated_data

        filters = CourseListFilters(
            search=(validated.get("search", "") or "").strip(),
            category_slugs=tuple(validated.get("category", ()) or ()),
            difficulty=tuple(validated.get("difficulty", ()) or ()),
            instructor_username=validated.get("instructor", "") or "",
            ordering=validated.get("ordering", CourseListFilters.ordering),
            scope=validated.get("scope", CourseScope.PUBLIC),
        )
        if filters.scope == CourseScope.MINE and not request.user.is_authenticated:
            raise NotAuthenticated

        viewer_id, viewer_is_staff = _viewer(request)
        queryset = course_selector.list_courses(
            filters=filters, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        return self.paginated_response(queryset, CourseListItemSerializer)

    @extend_schema(
        request=CourseCreateSerializer,
        responses={201: CourseDetailSerializer},
        tags=["courses"],
    )
    def post(self, request: Request) -> Response:
        """Create a course as a draft."""
        serializer = CourseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        course = course_service.create_course(
            instructor_id=request.user.id, data=serializer.validated_data
        )
        return Response(
            CourseDetailSerializer(course, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class CourseDetailView(ServiceAPIView):
    """Read, update or delete one course."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for writes."""
        if self.request.method in {"PATCH", "PUT", "DELETE"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: CourseDetailSerializer}, tags=["courses"])
    def get(self, request: Request, slug: str) -> Response:
        """Return one course; hidden and absent are the same 404."""
        viewer_id, viewer_is_staff = _viewer(request)
        course = course_service.get_course(
            slug=slug, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
        )
        return Response(
            CourseDetailSerializer(course, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CourseUpdateSerializer,
        responses={200: CourseDetailSerializer},
        tags=["courses"],
    )
    def patch(self, request: Request, slug: str) -> Response:
        """Partially update a course."""
        serializer = CourseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        course = course_service.update_course(
            slug=slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(
            CourseDetailSerializer(course, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["courses"])
    def delete(self, request: Request, slug: str) -> Response:
        """Permanently delete a course; archiving is the reversible option."""
        course_service.delete_course(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
