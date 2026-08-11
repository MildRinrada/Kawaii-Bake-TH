"""Read-side queries for notifications and preferences.

Every owner-facing read filters by recipient  there is structurally no
way to address another user's notification, so "not yours" and "does not
exist" are the same 404 at the API. The one exception is
:func:`list_all`, which serves only the ``IsAdminUser``-gated views.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.notifications.constants import NotificationEventType
from apps.notifications.models import Notification, NotificationPreference


def list_all(
    *, search: str = "", event_type: str = "", unread: bool | None = None
) -> QuerySet[Notification]:
    """Every notification across recipients, for the staff surface only.

    Args:
        search: Matches the title, body or the recipient's handle.
        event_type: Restrict to one :class:`NotificationEventType`.
        unread: ``True`` for unread rows, ``False`` for read, ``None`` both.

    Returns:
        A lazy queryset with the recipient preloaded, newest first.
    """
    queryset = Notification.objects.select_related("recipient__profile")

    if event_type:
        queryset = queryset.filter(event_type=event_type)
    if unread is True:
        queryset = queryset.filter(read_at__isnull=True)
    elif unread is False:
        queryset = queryset.filter(read_at__isnull=False)

    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(title__icontains=cleaned)
            | Q(body__icontains=cleaned)
            | Q(recipient__username__icontains=cleaned)
        )
    return queryset.order_by("-created_at", "-id")


def list_for_user(
    *, user_id: int, unread_only: bool = False
) -> QuerySet[Notification]:
    """The user's notifications, newest first.

    Args:
        user_id: Primary key of the recipient.
        unread_only: Restrict to unread rows.

    Returns:
        A lazy queryset; the paginator slices it at the API edge.
    """
    queryset = Notification.objects.filter(recipient_id=user_id)
    if unread_only:
        queryset = queryset.filter(read_at__isnull=True)
    return queryset


def unread_count(*, user_id: int) -> int:
    """How many of the user's notifications are unread.

    Computed live  there is deliberately no counter column to drift.

    Args:
        user_id: Primary key of the recipient.

    Returns:
        The unread count.
    """
    return Notification.objects.filter(
        recipient_id=user_id, read_at__isnull=True
    ).count()


def get_owned(
    *, notification_id: int, user_id: int
) -> Notification | None:
    """Fetch one notification, restricted to its recipient.

    Args:
        notification_id: Primary key of the notification.
        user_id: Primary key of the caller.

    Returns:
        The notification, or ``None`` when absent or not the caller's.
    """
    return Notification.objects.filter(
        pk=notification_id, recipient_id=user_id
    ).first()


def is_event_enabled(*, user_id: int, event_type: str) -> bool:
    """Whether the recipient accepts this event type.

    Absent row means enabled  the default costs no storage.

    Args:
        user_id: Primary key of the recipient.
        event_type: A value of :class:`NotificationEventType`.

    Returns:
        ``True`` unless an explicit opt-out row exists.
    """
    return not NotificationPreference.objects.filter(
        user_id=user_id, event_type=event_type, enabled=False
    ).exists()


def effective_preferences(*, user_id: int) -> dict[str, bool]:
    """Every supported event type with its effective state.

    Args:
        user_id: Primary key of the user.

    Returns:
        Mapping of event type to enabled, defaults filled in.
    """
    stored = dict(
        NotificationPreference.objects.filter(user_id=user_id).values_list(
            "event_type", "enabled"
        )
    )
    return {
        event_type: stored.get(event_type, True)
        for event_type in NotificationEventType.values
    }
