"""Staff notification routes, mounted at ``/api/v1/admin/notifications/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.notifications.api.views.admin_views import (
    AdminAudienceEstimateView,
    AdminBroadcastView,
    AdminCampaignAnalyticsView,
    AdminCampaignCancelView,
    AdminCampaignDetailView,
    AdminCampaignListView,
    AdminCampaignSendView,
    AdminNotificationListView,
    AdminNotificationStatsView,
    AdminTemplateDetailView,
    AdminTemplateListView,
)

app_name = "notifications_admin"

urlpatterns = [
    path("", AdminNotificationListView.as_view(), name="list"),
    path("broadcast/", AdminBroadcastView.as_view(), name="broadcast"),
    path("stats/", AdminNotificationStatsView.as_view(), name="stats"),
    path("campaigns/", AdminCampaignListView.as_view(), name="campaigns"),
    path(
        "campaigns/<int:campaign_id>/",
        AdminCampaignDetailView.as_view(),
        name="campaign-detail",
    ),
    path(
        "campaigns/<int:campaign_id>/send/",
        AdminCampaignSendView.as_view(),
        name="campaign-send",
    ),
    path(
        "campaigns/<int:campaign_id>/cancel/",
        AdminCampaignCancelView.as_view(),
        name="campaign-cancel",
    ),
    path(
        "campaigns/<int:campaign_id>/analytics/",
        AdminCampaignAnalyticsView.as_view(),
        name="campaign-analytics",
    ),
    path(
        "audience/estimate/",
        AdminAudienceEstimateView.as_view(),
        name="audience-estimate",
    ),
    path("templates/", AdminTemplateListView.as_view(), name="templates"),
    path(
        "templates/<int:template_id>/",
        AdminTemplateDetailView.as_view(),
        name="template-detail",
    ),
]
