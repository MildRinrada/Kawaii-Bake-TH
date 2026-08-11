"""Staff-only cross-user progress endpoints.

The ``admin/`` URL prefix is a naming convention, not the permission:
every view here declares ``IsAdminUser`` itself (ADR 0022), so a future
re-mount cannot accidentally expose them.

Enrollment data comes through the courses app's public selectors and
the lesson denominator through the lessons app's - this app still never
touches another app's models (ADR 0008).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.courses.selectors import course_selector, enrollment_selector
from apps.lessons.selectors import lesson_selector
from apps.progress.api.serializers.admin_serializers import (
    CourseStatFilterSerializer,
    CourseStatRowSerializer,
    LearnerFilterSerializer,
    LearnerRowSerializer,
    ProgressSummarySerializer,
)
from apps.progress.exceptions import ProgressCourseNotFoundError
from apps.progress.selectors import admin_progress_selector


class AdminProgressSummaryView(ServiceAPIView):
    """Headline learning totals for the dashboard's top strip."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: ProgressSummarySerializer}, tags=["progress-admin"]
    )
    def get(self, request: Request) -> Response:
        """Return platform-wide enrollment and completion counters."""
        counts = enrollment_selector.platform_enrollment_counts()
        return Response(
            {
                "enrollments_total": counts["total"],
                "enrollments_active": counts["active"],
                "enrollments_completed": counts["completed"],
                "enrollments_dropped": counts["dropped"],
                "learners": counts["learners"],
                "lessons_completed": (
                    admin_progress_selector.total_completed_lessons()
                ),
                "active_learners_7d": (
                    admin_progress_selector.active_learner_count(days=7)
                ),
            },
            status=status.HTTP_200_OK,
        )


class AdminCourseStatsView(PaginatedServiceAPIView):
    """Per-course enrollment funnels, most enrolled first."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[OpenApiParameter("search", str)],
        responses={200: CourseStatRowSerializer(many=True)},
        tags=["progress-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of courses with their enrollment counts."""
        filters = CourseStatFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = enrollment_selector.list_course_enrollment_stats(
            search=filters.validated_data.get("search", "")
        )
        return self.paginated_response(queryset, CourseStatRowSerializer)


class AdminCourseLearnersView(PaginatedServiceAPIView):
    """One course's learner roster with per-learner progress."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("search", str),
        ],
        responses={200: LearnerRowSerializer(many=True)},
        tags=["progress-admin"],
    )
    def get(self, request: Request, slug: str) -> Response:
        """Return a page of learners, newest enrollment first.

        Progress figures are merged in for the page only: two batch
        queries per page, never per row.

        Raises:
            ProgressCourseNotFoundError: If no course has that slug.
        """
        filters = LearnerFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data

        course = course_selector.get_course_ref(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=True
        )
        if course is None:
            raise ProgressCourseNotFoundError

        queryset = enrollment_selector.list_enrollments_for_course(
            course_id=course.id,
            enrollment_status=values.get("status", ""),
            search=values.get("search", ""),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        rows = list(page or [])
        user_ids = [row.user_id for row in rows]
        total = len(lesson_selector.published_lesson_ids(course_id=course.id))
        done = admin_progress_selector.completed_counts_for_users(
            course_id=course.id, user_ids=user_ids
        )
        seen = admin_progress_selector.last_activity_for_users(
            course_id=course.id, user_ids=user_ids
        )

        def build(row: Any) -> dict[str, Any]:
            profile = getattr(row.user, "profile", None)
            avatar = getattr(profile, "avatar", None) if profile else None
            completed = done.get(row.user_id, 0)
            return {
                "username": row.user.username,
                "display_name": (
                    (profile.display_name if profile else "") or row.user.username
                ),
                "avatar_url": (
                    request.build_absolute_uri(avatar.url) if avatar else None
                ),
                "status": row.status,
                "enrolled_at": row.enrolled_at,
                "completed_at": row.completed_at,
                "completed_lessons": completed,
                "total_lessons": total,
                "percent": round(completed * 100 / total) if total else 0,
                "last_activity_at": seen.get(row.user_id),
            }

        data = LearnerRowSerializer(
            [build(row) for row in rows], many=True
        ).data
        return self.paginator.get_paginated_response(data)
