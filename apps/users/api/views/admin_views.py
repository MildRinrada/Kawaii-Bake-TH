"""Staff-only account-management endpoints.

The ``admin/`` URL prefix is a naming convention, not the permission:
every view here declares ``IsAdminUser`` itself (ADR 0022), so a future
re-mount cannot accidentally expose them.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.users.api.serializers.admin_serializers import (
    AdminUserFilterSerializer,
    AdminUserSerializer,
    AdminUserStatsSerializer,
    AdminUserUpdateSerializer,
)
from apps.users.selectors import admin_user_selector
from apps.users.services import admin_user_service


class AdminUserStatsView(ServiceAPIView):
    """Headline account numbers for the roster's summary cards."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: AdminUserStatsSerializer}, tags=["users-admin"]
    )
    def get(self, request: Request) -> Response:
        """Return total/active/pending/suspended/staff/new counts."""
        return Response(admin_user_selector.roster_stats())


class AdminUserListView(PaginatedServiceAPIView):
    """The user roster."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str),
            OpenApiParameter("status", str),
            OpenApiParameter("verified", bool),
            OpenApiParameter("staff", bool),
            OpenApiParameter("ordering", str),
        ],
        responses={200: AdminUserSerializer(many=True)},
        tags=["users-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of accounts, newest first by default."""
        filters = AdminUserFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = admin_user_selector.list_users(
            search=values.get("search", ""),
            account_status=values.get("status", ""),
            verified=values.get("verified"),
            staff=values.get("staff"),
            joined_days=values.get("joined_days"),
            ordering=values.get("ordering") or "newest",
        )
        return self.paginated_response(queryset, AdminUserSerializer)


class AdminUserDetailView(ServiceAPIView):
    """One account: full detail and staff edits."""

    permission_classes = (IsAdminUser,)

    @extend_schema(responses={200: AdminUserSerializer}, tags=["users-admin"])
    def get(self, request: Request, user_id: int) -> Response:
        """Return one account.

        Raises:
            UserNotFoundError: If the account does not exist.
        """
        user = admin_user_service.get_account(user_id=user_id)
        return Response(
            AdminUserSerializer(user, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AdminUserUpdateSerializer,
        responses={200: AdminUserSerializer},
        tags=["users-admin"],
    )
    def patch(self, request: Request, user_id: int) -> Response:
        """Apply a staff edit - legal name, suspension, staff flag, or the
        emergency email-verification override.

        Raises:
            UserNotFoundError: If the account does not exist.
            ProtectedAccountError: If the edit touches the caller's own
                access flags or any flag of a superuser.
        """
        serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = admin_user_service.update_account(
            actor_id=request.user.id,
            user_id=user_id,
            changes=serializer.validated_data,
        )
        return Response(
            AdminUserSerializer(user, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )
