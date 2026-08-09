"""Test data builders for the notification domain."""

from __future__ import annotations

from typing import Any

from apps.notifications.constants import NotificationEventType
from apps.notifications.models import Notification


def create_notification(
    *,
    recipient: Any,
    event_type: str = NotificationEventType.REVIEW_RECEIVED,
    title: str = "มีรีวิวใหม่บนสูตรของคุณ",
    **extra: Any,
) -> Notification:
    """Create a notification directly at the model layer."""
    return Notification.objects.create(
        recipient=recipient,
        event_type=event_type,
        title=title,
        body=extra.pop("body", "ทดสอบ 🎂"),
        **extra,
    )
