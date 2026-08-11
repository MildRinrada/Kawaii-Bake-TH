"""Staff-only favorites reads.

Read-only by design: a favorite is a user's private signal, so staff can
observe the aggregate (what is popular, who saved what) but there is no
write path - deleting someone's favorite would be editing their taste.

The ``admin/`` URL prefix is a naming convention, not the permission:
every view here declares ``IsAdminUser`` itself (ADR 0022).
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.favorites.api.serializers.admin_serializers import (
    AdminFavoriteFilterSerializer,
    AdminFavoriteSerializer,
    FavoriteTopSerializer,
)
from apps.favorites.selectors import favorite_selector


class AdminFavoriteListView(PaginatedServiceAPIView):
    """Every favorite across users, newest first."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("type", str),
            OpenApiParameter("search", str),
        ],
        responses={200: AdminFavoriteSerializer(many=True)},
        tags=["favorites-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of favorites."""
        filters = AdminFavoriteFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = favorite_selector.list_all_favorites(
            kind=values.get("type", ""),
            search=values.get("search", ""),
        )
        return self.paginated_response(queryset, AdminFavoriteSerializer)


class AdminFavoriteTopView(ServiceAPIView):
    """The most-favorited recipes and courses, computed live."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: FavoriteTopSerializer}, tags=["favorites-admin"]
    )
    def get(self, request: Request) -> Response:
        """Return the top-ten rankings for both target kinds."""
        return Response(
            {
                "recipes": favorite_selector.top_favorited_recipes(),
                "courses": favorite_selector.top_favorited_courses(),
            },
            status=status.HTTP_200_OK,
        )
