"""Staff-only notification endpoints: the cross-user log and broadcast.

The ``admin/`` URL prefix is a naming convention, not the permission:
every view here declares ``IsAdminUser`` itself (ADR 0022), so a future
re-mount cannot accidentally expose them.

Notifications are in-app only - there is no email channel here, so
"delivered" means the row exists and ``read_at`` is the only receipt
the platform can honestly report.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.notifications.api.serializers.admin_serializers import (
    AdminNotificationFilterSerializer,
    AdminNotificationSerializer,
    BroadcastResultSerializer,
    BroadcastSerializer,
)
from apps.notifications.selectors import notification_selector
from apps.notifications.services import notification_service


class AdminNotificationListView(PaginatedServiceAPIView):
    """Every notification across recipients, newest first."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str),
            OpenApiParameter("event_type", str),
            OpenApiParameter("unread", bool),
        ],
        responses={200: AdminNotificationSerializer(many=True)},
        tags=["notifications-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of notifications with their read state."""
        filters = AdminNotificationFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = notification_selector.list_all(
            search=values.get("search", ""),
            event_type=values.get("event_type", ""),
            unread=values.get("unread"),
        )
        return self.paginated_response(queryset, AdminNotificationSerializer)


class AdminBroadcastView(ServiceAPIView):
    """Send one announcement to every active account."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=BroadcastSerializer,
        responses={201: BroadcastResultSerializer},
        tags=["notifications-admin"],
    )
    def post(self, request: Request) -> Response:
        """Broadcast an announcement, honouring per-user opt-outs."""
        serializer = BroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        recipients = notification_service.broadcast_announcement(
            actor_id=request.user.id,
            title=values["title"],
            body=values.get("body", ""),
            link=values.get("link", ""),
        )
        return Response(
            {"recipients": recipients}, status=status.HTTP_201_CREATED
        )
