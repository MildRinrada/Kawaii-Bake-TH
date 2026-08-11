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
    AdminNotificationStatsSerializer,
    AudienceEstimateResultSerializer,
    AudienceEstimateSerializer,
    BroadcastResultSerializer,
    BroadcastSerializer,
    CampaignAnalyticsSerializer,
    CampaignFilterSerializer,
    CampaignSerializer,
    CampaignWriteSerializer,
    TemplateItemSerializer,
    TemplateWriteSerializer,
)
from apps.notifications.exceptions import CampaignNotFoundError
from apps.notifications.selectors import notification_selector
from apps.notifications.services import campaign_service, notification_service


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


# --------------------------------------------------------------------------
# Campaigns and templates (ADR 0030)
# --------------------------------------------------------------------------


class AdminNotificationStatsView(ServiceAPIView):
    """Headline numbers for the staff notifications hub."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: AdminNotificationStatsSerializer},
        tags=["notifications-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return campaign counts, today's deliveries, and read totals."""
        return Response(notification_selector.admin_stats())


class AdminCampaignListView(PaginatedServiceAPIView):
    """The tabbed campaign list, plus campaign creation."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("search", str),
        ],
        responses={200: CampaignSerializer(many=True)},
        tags=["notifications-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of campaigns, newest first."""
        filters = CampaignFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = notification_selector.list_campaigns(
            status=values.get("status", ""), search=values.get("search", "")
        )
        return self.paginated_response(queryset, CampaignSerializer)

    @extend_schema(
        request=CampaignWriteSerializer,
        responses={201: CampaignSerializer},
        tags=["notifications-admin"],
    )
    def post(self, request: Request) -> Response:
        """Create a campaign as a draft, or directly scheduled."""
        serializer = CampaignWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        campaign = campaign_service.create_campaign(
            actor_id=request.user.id,
            audience=values.pop("audience"),
            status=values.pop("status"),
            scheduled_at=values.pop("scheduled_at", None),
            **values,
        )
        row = notification_selector.get_campaign(campaign_id=campaign.pk)
        return Response(
            CampaignSerializer(row).data, status=status.HTTP_201_CREATED
        )


class AdminCampaignDetailView(ServiceAPIView):
    """One campaign: read, edit (draft/scheduled), delete (draft/canceled)."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: CampaignSerializer}, tags=["notifications-admin"]
    )
    def get(self, request: Request, campaign_id: int) -> Response:
        """Return one campaign."""
        campaign = notification_selector.get_campaign(campaign_id=campaign_id)
        if campaign is None:
            raise CampaignNotFoundError
        return Response(CampaignSerializer(campaign).data)

    @extend_schema(
        request=CampaignWriteSerializer,
        responses={200: CampaignSerializer},
        tags=["notifications-admin"],
    )
    def patch(self, request: Request, campaign_id: int) -> Response:
        """Edit a draft or scheduled campaign."""
        serializer = CampaignWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        campaign_service.update_campaign(
            campaign_id=campaign_id,
            audience=values.pop("audience", None),
            status=values.pop("status", None),
            scheduled_at=values.pop("scheduled_at", None),
            **values,
        )
        row = notification_selector.get_campaign(campaign_id=campaign_id)
        return Response(CampaignSerializer(row).data)

    @extend_schema(responses={204: None}, tags=["notifications-admin"])
    def delete(self, request: Request, campaign_id: int) -> Response:
        """Delete a draft or canceled campaign."""
        campaign_service.delete_campaign(campaign_id=campaign_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCampaignSendView(ServiceAPIView):
    """Deliver a draft or scheduled campaign now."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=None,
        responses={200: BroadcastResultSerializer},
        tags=["notifications-admin"],
    )
    def post(self, request: Request, campaign_id: int) -> Response:
        """Send the campaign and report how many recipients it reached."""
        recipients = campaign_service.send_campaign(
            campaign_id=campaign_id, actor_id=request.user.id
        )
        return Response({"recipients": recipients})


class AdminCampaignCancelView(ServiceAPIView):
    """Call off a scheduled send."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=None,
        responses={200: CampaignSerializer},
        tags=["notifications-admin"],
    )
    def post(self, request: Request, campaign_id: int) -> Response:
        """Cancel the schedule and return the campaign."""
        campaign_service.cancel_campaign(campaign_id=campaign_id)
        row = notification_selector.get_campaign(campaign_id=campaign_id)
        return Response(CampaignSerializer(row).data)


class AdminCampaignAnalyticsView(ServiceAPIView):
    """Delivery analytics for one campaign - real receipts only."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: CampaignAnalyticsSerializer},
        tags=["notifications-admin"],
    )
    def get(self, request: Request, campaign_id: int) -> Response:
        """Return delivered/read counts and the read rate."""
        campaign = notification_selector.get_campaign(campaign_id=campaign_id)
        if campaign is None:
            raise CampaignNotFoundError
        stats = notification_selector.campaign_delivery_stats(
            campaign_id=campaign_id
        )
        delivered = stats["delivered"]
        read = stats["read"]
        return Response(
            {
                "recipients": campaign.recipients_count or 0,
                "delivered": delivered,
                "read": read,
                "unread": delivered - read,
                "read_rate": (read / delivered) if delivered else 0.0,
                "sent_at": campaign.sent_at,
            }
        )


class AdminAudienceEstimateView(ServiceAPIView):
    """Recipient-count estimate for the composer, pre-send."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=AudienceEstimateSerializer,
        responses={200: AudienceEstimateResultSerializer},
        tags=["notifications-admin"],
    )
    def post(self, request: Request) -> Response:
        """Resolve the audience the same way a send would, and count it."""
        serializer = AudienceEstimateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = campaign_service.estimate_audience(
            audience=serializer.validated_data["audience"]
        )
        return Response({"count": count})


class AdminTemplateListView(ServiceAPIView):
    """Reusable composer templates: the full list, plus creation."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: TemplateItemSerializer(many=True)},
        tags=["notifications-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return every template, active first."""
        queryset = notification_selector.list_templates()
        return Response(TemplateItemSerializer(queryset, many=True).data)

    @extend_schema(
        request=TemplateWriteSerializer,
        responses={201: TemplateItemSerializer},
        tags=["notifications-admin"],
    )
    def post(self, request: Request) -> Response:
        """Create a template."""
        serializer = TemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        values.pop("is_archived", None)
        template = campaign_service.create_template(
            actor_id=request.user.id, **values
        )
        return Response(
            TemplateItemSerializer(template).data,
            status=status.HTTP_201_CREATED,
        )


class AdminTemplateDetailView(ServiceAPIView):
    """One template: edit, archive/unarchive, delete."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=TemplateWriteSerializer,
        responses={200: TemplateItemSerializer},
        tags=["notifications-admin"],
    )
    def patch(self, request: Request, template_id: int) -> Response:
        """Edit a template's fields or archived flag."""
        serializer = TemplateWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        template = campaign_service.update_template(
            template_id=template_id,
            is_archived=values.pop("is_archived", None),
            **values,
        )
        return Response(TemplateItemSerializer(template).data)

    @extend_schema(responses={204: None}, tags=["notifications-admin"])
    def delete(self, request: Request, template_id: int) -> Response:
        """Delete a template."""
        campaign_service.delete_template(template_id=template_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
