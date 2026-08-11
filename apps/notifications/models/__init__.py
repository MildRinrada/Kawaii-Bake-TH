"""Notifications models - public API."""

from __future__ import annotations

from apps.notifications.models.campaign import (
    NotificationCampaign,
    NotificationTemplate,
)
from apps.notifications.models.notification import Notification
from apps.notifications.models.preference import NotificationPreference

__all__ = [
    "Notification",
    "NotificationCampaign",
    "NotificationPreference",
    "NotificationTemplate",
]
