"""Read-side queries for notifications and preferences.

Every owner-facing read filters by recipient  there is structurally no
way to address another user's notification, so "not yours" and "does not
exist" are the same 404 at the API. The one exception is
:func:`list_all`, which serves only the ``IsAdminUser``-gated views.
"""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.notifications.constants import CampaignStatus, NotificationEventType
from apps.notifications.models import (
    Notification,
    NotificationCampaign,
    NotificationPreference,
    NotificationTemplate,
)


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


# --------------------------------------------------------------------------
# Campaigns and templates (ADR 0030) - staff surface only
# --------------------------------------------------------------------------


def list_campaigns(
    *, status: str = "", search: str = ""
) -> QuerySet[NotificationCampaign]:
    """Campaigns for the tabbed staff list, newest first.

    Args:
        status: Restrict to one :class:`CampaignStatus`, or all when blank.
        search: Matches the title or body.

    Returns:
        A lazy queryset with the author preloaded.
    """
    queryset = NotificationCampaign.objects.select_related(
        "created_by"
    ).annotate(
        read_count=Count(
            "deliveries", filter=Q(deliveries__read_at__isnull=False)
        )
    )
    if status:
        queryset = queryset.filter(status=status)
    cleaned = search.strip()
    if cleaned:
        queryset = queryset.filter(
            Q(title__icontains=cleaned) | Q(body__icontains=cleaned)
        )
    return queryset.order_by("-created_at", "-id")


def get_campaign(*, campaign_id: int) -> NotificationCampaign | None:
    """Fetch one campaign with its author preloaded.

    Args:
        campaign_id: Primary key of the campaign.

    Returns:
        The campaign, or ``None`` when absent.
    """
    return (
        NotificationCampaign.objects.select_related("created_by")
        .annotate(
            read_count=Count(
                "deliveries", filter=Q(deliveries__read_at__isnull=False)
            ),
            click_count=Count(
                "deliveries", filter=Q(deliveries__clicked_at__isnull=False)
            ),
        )
        .filter(pk=campaign_id)
        .first()
    )


def campaign_delivery_stats(*, campaign_id: int) -> dict[str, int]:
    """Honest delivery analytics: rows created, read, and followed.

    In-app only, so "delivered" means the snapshot exists. ``read`` is a
    real receipt (the reader opened the centre or the bell panel).
    ``clicked`` is reported by the recipient's browser as it navigates,
    which makes it a **floor**: a middle-click, a copied link or a
    blocked script is a click nobody records. The panel labels it that
    way rather than presenting it as a measurement.

    Args:
        campaign_id: Primary key of the campaign.

    Returns:
        Mapping with ``delivered``, ``read`` and ``clicked`` counts.
    """
    row = Notification.objects.filter(campaign_id=campaign_id).aggregate(
        delivered=Count("id"),
        read=Count("id", filter=Q(read_at__isnull=False)),
        clicked=Count("id", filter=Q(clicked_at__isnull=False)),
    )
    return {
        "delivered": row["delivered"],
        "read": row["read"],
        "clicked": row["clicked"],
    }


def list_templates(
    *, include_archived: bool = True
) -> QuerySet[NotificationTemplate]:
    """Composer templates, active first, then by name.

    Args:
        include_archived: Whether archived templates are included.

    Returns:
        A lazy queryset.
    """
    queryset = NotificationTemplate.objects.all()
    if not include_archived:
        queryset = queryset.filter(is_archived=False)
    return queryset


def get_template(*, template_id: int) -> NotificationTemplate | None:
    """Fetch one template.

    Args:
        template_id: Primary key of the template.

    Returns:
        The template, or ``None`` when absent.
    """
    return NotificationTemplate.objects.filter(pk=template_id).first()


def admin_stats() -> dict[str, int]:
    """Headline numbers for the staff notifications hub.

    Every figure is a real count: campaigns by status, snapshots
    delivered today, and the platform-wide read receipts.

    Returns:
        Mapping with campaign counts, today's deliveries, and the
        delivered/read totals the read-rate is computed from.
    """
    by_status = dict(
        NotificationCampaign.objects.values_list("status").annotate(
            total=Count("id")
        )
    )
    today_start = timezone.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    receipts = Notification.objects.aggregate(
        delivered=Count("id"),
        read=Count("id", filter=Q(read_at__isnull=False)),
        clicked=Count("id", filter=Q(clicked_at__isnull=False)),
    )
    return {
        "campaigns_sent": by_status.get(CampaignStatus.SENT, 0),
        "drafts": by_status.get(CampaignStatus.DRAFT, 0),
        "scheduled": by_status.get(CampaignStatus.SCHEDULED, 0),
        "sent_today": Notification.objects.filter(
            created_at__gte=today_start
        ).count(),
        "delivered_total": receipts["delivered"],
        "read_total": receipts["read"],
        "clicked_total": receipts["clicked"],
    }
