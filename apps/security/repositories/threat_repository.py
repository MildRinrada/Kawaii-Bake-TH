"""The single mutation choke point for security rows.

Nothing outside this module calls ``save()``, ``create()`` or ``update()``
on :class:`SecurityEvent` or :class:`ThreatProfile`. Keeping the writes in
one file is what makes the "profile is always derived from its events"
claim checkable by reading rather than by hoping.
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction

from apps.security import blocklist
from apps.security.constants import (
    NOTE_MAX_LENGTH,
    PATH_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    ReviewState,
)
from apps.security.models import SecurityEvent, ThreatProfile


def truncate(value: str, limit: int) -> str:
    """Clip attacker-controlled text to a column's width.

    Args:
        value: Raw text from the request.
        limit: Maximum stored length.

    Returns:
        ``value`` clipped to ``limit`` characters.
    """
    return value[:limit] if value else ""


@transaction.atomic
def record_event(
    *,
    kind: str,
    severity: str,
    score_delta: float,
    ip: str,
    user_agent: str = "",
    path: str = "",
    method: str = "",
    status_code: int | None = None,
    actor_id: int | None = None,
    request_id: str = "",
    detail: dict | None = None,
) -> SecurityEvent:
    """Append one immutable observation.

    Args:
        kind: A :class:`~apps.security.constants.SignalKind` value.
        severity: The band this single observation rates on its own.
        score_delta: Points added to the offender's profile.
        ip: Source address.
        user_agent: Raw user agent, truncated to the column width.
        path: Request path, truncated to the column width.
        method: HTTP method.
        status_code: Response status, when known.
        actor_id: The signed-in user, when there was one.
        request_id: Correlation id from ``RequestIDMiddleware``.
        detail: Detector context (which marker matched, and so on).

    Returns:
        The created event.
    """
    return SecurityEvent.objects.create(
        kind=kind,
        severity=severity,
        score_delta=score_delta,
        ip=ip,
        user_agent=truncate(user_agent, USER_AGENT_MAX_LENGTH),
        path=truncate(path, PATH_MAX_LENGTH),
        method=method[:10],
        status_code=status_code,
        actor_id=actor_id,
        request_id=request_id[:40],
        detail=detail or {},
    )


def lock_profile(*, ip: str, now: datetime) -> ThreatProfile:
    """Fetch the profile for ``ip`` for update, creating it if absent.

    ``select_for_update`` is what makes concurrent scoring correct: two
    workers observing the same attacker at the same instant must not both
    read the old score and write back the same new one.

    Args:
        ip: Source address.
        now: Timestamp used for a newly created row's ``last_seen_at``.

    Returns:
        The locked profile.
    """
    profile, _created = ThreatProfile.objects.get_or_create(
        ip=ip, defaults={"last_seen_at": now}
    )
    # get_or_create cannot take the lock itself; re-read under it.
    return ThreatProfile.objects.select_for_update().get(pk=profile.pk)


def apply_score(
    *,
    profile: ThreatProfile,
    score: float,
    level: str,
    now: datetime,
    last_kind: str,
    last_path: str,
    last_user_agent: str,
) -> ThreatProfile:
    """Write a recomputed score and its band back to the profile.

    ``score`` and ``level`` are always written together — the whole point
    of storing both is that they agree.

    Args:
        profile: A profile already locked by :func:`lock_profile`.
        score: The new decayed-and-incremented score.
        level: The band ``score`` falls into.
        now: Observation time.
        last_kind: Kind of the observation that caused this write.
        last_path: Its path.
        last_user_agent: Its user agent.

    Returns:
        The saved profile.
    """
    profile.score = score
    profile.level = level
    profile.event_count += 1
    profile.last_seen_at = now
    profile.last_kind = last_kind
    profile.last_path = truncate(last_path, PATH_MAX_LENGTH)
    profile.last_user_agent = truncate(last_user_agent, USER_AGENT_MAX_LENGTH)
    profile.save(
        update_fields=[
            "score",
            "level",
            "event_count",
            "last_seen_at",
            "last_kind",
            "last_path",
            "last_user_agent",
        ]
    )
    return profile


def set_block(
    *, profile: ThreatProfile, until: datetime | None, actor_id: int | None
) -> ThreatProfile:
    """Set or clear the block window.

    Args:
        profile: The profile to change.
        until: When the block lapses; ``None`` lifts it.
        actor_id: The staff user responsible, or ``None`` for automatic.

    Returns:
        The saved profile.
    """
    profile.blocked_until = until
    profile.blocked_by_id = actor_id
    profile.save(update_fields=["blocked_until", "blocked_by"])
    # The request path reads a cached set; drop it now so an operator's
    # block or unblock takes effect on the very next request rather than
    # when the cache happens to expire.
    blocklist.invalidate()
    return profile


def set_review(
    *,
    profile: ThreatProfile,
    state: str,
    reviewed_at: datetime,
    actor_id: int,
    note: str = "",
) -> ThreatProfile:
    """Record an operator's triage decision.

    Args:
        profile: The profile to change.
        state: A :class:`~apps.security.constants.ReviewState` value.
        reviewed_at: When the decision was made.
        actor_id: The staff user who made it.
        note: Optional free-text reason.

    Returns:
        The saved profile.
    """
    profile.review_state = state
    profile.reviewed_at = reviewed_at
    profile.reviewed_by_id = actor_id
    profile.note = truncate(note, NOTE_MAX_LENGTH)
    profile.save(
        update_fields=["review_state", "reviewed_at", "reviewed_by", "note"]
    )
    return profile


def reopen(*, profile: ThreatProfile) -> None:
    """Return a reviewed profile to the queue after fresh activity.

    An address an operator dismissed as benign that then trips a detector
    again is a new question, not a settled one.

    Args:
        profile: The profile to reopen.
    """
    if profile.review_state != ReviewState.OPEN:
        profile.review_state = ReviewState.OPEN
        profile.save(update_fields=["review_state"])
