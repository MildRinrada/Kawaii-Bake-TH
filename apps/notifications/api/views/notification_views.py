"""Notification endpoints  all owner-scoped, all authenticated.

There is deliberately no create endpoint here: notifications exist
because a producer service called ``notification_service.notify``. The
one human producer is the staff broadcast in ``admin_views``, which
still goes through the service layer like every other producer.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.notifications.api.serializers import (
    NotificationListSerializer,
    NotificationPreferencesSerializer,
    NotificationSerializer,
    ReadAllResultSerializer,
)
from apps.notifications.selectors import notification_selector
from apps.notifications.services import notification_service


class MyNotificationsView(PaginatedServiceAPIView):
    """The caller's notification feed."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: NotificationListSerializer}, tags=["notifications"]
    )
    def get(self, request: Request) -> Response:
        """Return a page, newest first, with the live unread count.

        ``?unread=true`` restricts to unread rows.
        """
        unread_only = request.query_params.get("unread") == "true"
        queryset = notification_selector.list_for_user(
            user_id=request.user.id, unread_only=unread_only
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        body = self.paginator.get_paginated_response(
            NotificationSerializer(page, many=True).data
        ).data
        body["unread_count"] = notification_selector.unread_count(
            user_id=request.user.id
        )
        return Response(body, status=status.HTTP_200_OK)


class NotificationReadView(ServiceAPIView):
    """Mark one notification read."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None,
        responses={200: NotificationSerializer},
        tags=["notifications"],
    )
    def post(self, request: Request, notification_id: int) -> Response:
        """Stamp ``read_at`` once; repeat calls stay 200."""
        notification = notification_service.mark_read(
            notification_id=notification_id, user_id=request.user.id
        )
        return Response(
            NotificationSerializer(notification).data, status=status.HTTP_200_OK
        )


class NotificationReadAllView(ServiceAPIView):
    """Mark everything read in one conditional bulk update."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None,
        responses={200: ReadAllResultSerializer},
        tags=["notifications"],
    )
    def post(self, request: Request) -> Response:
        """Return how many rows this call newly stamped."""
        marked = notification_service.mark_all_read(user_id=request.user.id)
        return Response({"marked_read": marked}, status=status.HTTP_200_OK)


class NotificationPreferencesView(ServiceAPIView):
    """Read and change the caller's per-event choices."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: NotificationPreferencesSerializer},
        tags=["notifications"],
    )
    def get(self, request: Request) -> Response:
        """Return every supported event type; absent rows read as enabled."""
        return Response(
            notification_selector.effective_preferences(user_id=request.user.id),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=NotificationPreferencesSerializer,
        responses={200: NotificationPreferencesSerializer},
        tags=["notifications"],
    )
    def patch(self, request: Request) -> Response:
        """Upsert the submitted event types; unknown keys are rejected."""
        serializer = NotificationPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        effective = notification_service.set_preferences(
            user_id=request.user.id, changes=serializer.validated_data
        )
        return Response(effective, status=status.HTTP_200_OK)
