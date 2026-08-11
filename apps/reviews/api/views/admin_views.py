"""Staff-only review moderation reads.

Only the flat list lives here: hide/show and delete reuse the public
``/reviews/{id}/`` routes, whose services already widen for staff. There
is deliberately no way to edit a review's text - the words belong to
their author; staff moderate visibility, never content.

The ``admin/`` URL prefix is a naming convention, not the permission:
the view declares ``IsAdminUser`` itself (ADR 0022).
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView
from apps.reviews.api.serializers.admin_serializers import (
    AdminReviewFilterSerializer,
    AdminReviewSerializer,
)
from apps.reviews.selectors import review_selector


class AdminReviewListView(PaginatedServiceAPIView):
    """Every review across recipes and courses, newest first."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("rating", int),
            OpenApiParameter("status", str),
            OpenApiParameter("target", str),
            OpenApiParameter("search", str),
        ],
        responses={200: AdminReviewSerializer(many=True)},
        tags=["reviews-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of reviews; deleted rows only when asked for."""
        filters = AdminReviewFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = review_selector.list_all(
            rating=values.get("rating"),
            review_status=values.get("status", ""),
            target=values.get("target", ""),
            search=values.get("search", ""),
            username=values.get("username", ""),
        )
        return self.paginated_response(queryset, AdminReviewSerializer)
