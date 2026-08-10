"""Read-side queries for the operator dashboard.

Every function here returns a lazy queryset or a plain dict; the ORM runs
at the API edge once the paginator has sliced. Nothing here writes, and
nothing here decides policy — the filters are exactly the facets the
dashboard offers, with unknown values ignored rather than erroring, so a
stale bookmark shows data instead of a 400.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.security.constants import (
    ReviewState,
    SignalKind,
    ThreatLevel,
)
from apps.security.models import SecurityEvent, ThreatProfile

#: Facet windows the dashboard offers, in hours.
SUMMARY_WINDOWS = (24, 168)


def list_events(
    *,
    kind: str = "",
    severity: str = "",
    ip: str = "",
    search: str = "",
    since_hours: int | None = None,
) -> QuerySet[SecurityEvent]:
    """The event log, newest first, narrowed by the dashboard's facets.

    Args:
        kind: Restrict to one :class:`SignalKind`.
        severity: Restrict to one :class:`ThreatLevel`.
        ip: Restrict to one exact source address.
        search: Substring match over path and user agent.
        since_hours: Only events newer than this many hours.

    Returns:
        A lazy queryset.
    """
    queryset = SecurityEvent.objects.select_related("actor")
    if kind in SignalKind.values:
        queryset = queryset.filter(kind=kind)
    if severity in ThreatLevel.values:
        queryset = queryset.filter(severity=severity)
    if ip:
        queryset = queryset.filter(ip=ip)
    if search:
        queryset = queryset.filter(
            Q(path__icontains=search) | Q(user_agent__icontains=search)
        )
    if since_hours:
        queryset = queryset.filter(
            created_at__gte=timezone.now() - timedelta(hours=since_hours)
        )
    return queryset


def list_profiles(
    *,
    level: str = "",
    review_state: str = "",
    blocked: bool | None = None,
    search: str = "",
    ordering: str = "-score",
) -> QuerySet[ThreatProfile]:
    """Offender profiles for the dashboard table.

    Args:
        level: Restrict to one :class:`ThreatLevel`.
        review_state: Restrict to one :class:`ReviewState`.
        blocked: ``True`` for currently blocked, ``False`` for not.
        search: Substring match over address, last path and user agent.
        ordering: ``-score`` (default) or ``-last_seen_at``.

    Returns:
        A lazy queryset.
    """
    queryset = ThreatProfile.objects.select_related("reviewed_by", "blocked_by")
    if level in ThreatLevel.values:
        queryset = queryset.filter(level=level)
    if review_state in ReviewState.values:
        queryset = queryset.filter(review_state=review_state)
    if blocked is not None:
        now = timezone.now()
        # "Blocked" means the window is still open — a lapsed block reads
        # as unblocked without anything having to sweep the table.
        condition = Q(blocked_until__gt=now)
        queryset = queryset.filter(condition) if blocked else queryset.exclude(condition)
    if search:
        queryset = queryset.filter(
            Q(ip__icontains=search)
            | Q(last_path__icontains=search)
            | Q(last_user_agent__icontains=search)
        )
    allowed_ordering = {"-score", "score", "-last_seen_at", "last_seen_at"}
    return queryset.order_by(
        ordering if ordering in allowed_ordering else "-score", "-last_seen_at"
    )


def get_profile(*, profile_id: int) -> ThreatProfile | None:
    """One profile by primary key.

    Args:
        profile_id: Primary key.

    Returns:
        The profile, or ``None``.
    """
    return (
        ThreatProfile.objects.select_related("reviewed_by", "blocked_by")
        .filter(pk=profile_id)
        .first()
    )


def recent_events_for_ip(*, ip: str, limit: int = 20) -> QuerySet[SecurityEvent]:
    """The newest events from one address, for the drill-down panel.

    Args:
        ip: Source address.
        limit: How many rows to return.

    Returns:
        A sliced queryset.
    """
    return SecurityEvent.objects.filter(ip=ip).select_related("actor")[:limit]


def summary() -> dict:
    """Headline counters for the dashboard's top strip.

    Computed live in a handful of aggregate queries. There is
    deliberately no stored counter: this is read by a few staff a few
    times a day, and a counter would be one more thing to drift.

    Returns:
        A dict of totals, per-band counts, per-kind counts and offenders.
    """
    now = timezone.now()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(hours=168)

    by_level = dict(
        ThreatProfile.objects.values_list("level")
        .annotate(total=Count("id"))
        .values_list("level", "total")
    )
    by_kind = dict(
        SecurityEvent.objects.filter(created_at__gte=week_ago)
        .values_list("kind")
        .annotate(total=Count("id"))
        .values_list("kind", "total")
    )

    top = list(
        ThreatProfile.objects.order_by("-score", "-last_seen_at").values(
            "id", "ip", "score", "level", "event_count", "last_seen_at", "last_kind"
        )[:5]
    )

    return {
        "generated_at": now,
        "profiles_total": ThreatProfile.objects.count(),
        "profiles_by_level": {
            level: by_level.get(level, 0) for level in ThreatLevel.values
        },
        "profiles_blocked": ThreatProfile.objects.filter(
            blocked_until__gt=now
        ).count(),
        "profiles_open": ThreatProfile.objects.filter(
            review_state=ReviewState.OPEN
        ).count(),
        "events_total": SecurityEvent.objects.count(),
        "events_24h": SecurityEvent.objects.filter(created_at__gte=day_ago).count(),
        "events_7d": SecurityEvent.objects.filter(created_at__gte=week_ago).count(),
        "events_by_kind_7d": {kind: by_kind.get(kind, 0) for kind in SignalKind.values},
        "top_offenders": top,
    }
