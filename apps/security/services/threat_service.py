"""Scoring and enforcement — the only place security state is decided."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from hmac import compare_digest

from django.db import transaction
from django.utils import timezone

from apps.security import config
from apps.security.constants import (
    CLIENT_REPORTABLE,
    EDGE_REPORTABLE,
    MAX_SCORE,
    SCORE_HALF_LIFE_HOURS,
    SIGNAL_WEIGHTS,
    ReviewState,
    SignalKind,
    ThreatLevel,
    level_for_score,
)
from apps.security.exceptions import (
    EdgeForwardingDisabledError,
    EdgeSecretMismatchError,
    SignalNotClientReportableError,
    SignalNotEdgeReportableError,
    ThreatProfileNotFoundError,
)
from apps.security.models import SecurityEvent, ThreatProfile
from apps.security.repositories import threat_repository

logger = logging.getLogger("kawaiibake.security")


def decayed_score(*, score: float, since: datetime, now: datetime) -> float:
    """Apply exponential decay to a stored score.

    Half-life decay rather than a fixed rolling window: an address that
    was hostile an hour ago should still look hostile, one that was
    hostile last week should not, and no cron job should be required to
    make that true. A profile ages correctly even if nothing ever reads
    it again.

    Args:
        score: The score as last stored.
        since: When it was last written.
        now: Current time.

    Returns:
        The score as of ``now``.
    """
    hours = max(0.0, (now - since).total_seconds() / 3600.0)
    if hours == 0.0:
        return score
    return score * (0.5 ** (hours / SCORE_HALF_LIFE_HOURS))


def current_score(profile: ThreatProfile, *, now: datetime | None = None) -> float:
    """The profile's score decayed to this instant.

    Args:
        profile: The profile to evaluate.
        now: Override for the current time.

    Returns:
        The decayed score.
    """
    return decayed_score(
        score=profile.score, since=profile.last_seen_at, now=now or timezone.now()
    )


def record(
    *,
    kind: str,
    ip: str,
    user_agent: str = "",
    path: str = "",
    method: str = "",
    status_code: int | None = None,
    actor_id: int | None = None,
    request_id: str = "",
    detail: dict | None = None,
) -> SecurityEvent | None:
    """Score one observation and append its evidence.

    Returns ``None`` — without raising — when watching is disabled or the
    address is trusted. Callers sit on the request path, so "nothing to
    do" must be cheap and silent.

    Args:
        kind: A :class:`SignalKind` value.
        ip: Source address.
        user_agent: Raw user agent.
        path: Request path.
        method: HTTP method.
        status_code: Response status, when known.
        actor_id: Signed-in user, when there was one.
        request_id: Correlation id.
        detail: Detector context.

    Returns:
        The recorded event, or ``None`` when nothing was recorded.
    """
    if not config.watch_enabled():
        return None
    if not ip or ip in config.trusted_ips():
        return None

    weight = float(SIGNAL_WEIGHTS[kind])
    now = timezone.now()

    with transaction.atomic():
        profile = threat_repository.lock_profile(ip=ip, now=now)
        score = min(
            MAX_SCORE,
            decayed_score(score=profile.score, since=profile.last_seen_at, now=now)
            + weight,
        )
        level = level_for_score(score)
        threat_repository.apply_score(
            profile=profile,
            score=score,
            level=level,
            now=now,
            last_kind=kind,
            last_path=path,
            last_user_agent=user_agent,
        )
        threat_repository.reopen(profile=profile)

        event = threat_repository.record_event(
            kind=kind,
            # A single observation's own severity, independent of history:
            # one honeypot hit is "high" whether or not the address has a
            # past. The profile carries the accumulated verdict.
            severity=level_for_score(weight),
            score_delta=weight,
            ip=ip,
            user_agent=user_agent,
            path=path,
            method=method,
            status_code=status_code,
            actor_id=actor_id,
            request_id=request_id,
            detail=detail,
        )

        if (
            config.auto_block_enabled()
            and level == ThreatLevel.CRITICAL
            and not is_blocked(profile, now=now)
        ):
            threat_repository.set_block(
                profile=profile,
                until=now + timedelta(minutes=config.auto_block_minutes()),
                actor_id=None,
            )
            logger.warning(
                "security: auto-blocked %s after %s (score %.1f)", ip, kind, score
            )

    return event


def record_client_signal(
    *,
    kind: str,
    ip: str,
    user_agent: str = "",
    path: str = "",
    actor_id: int | None = None,
    request_id: str = "",
    detail: dict | None = None,
) -> SecurityEvent | None:
    """Record a signal a browser reported about itself.

    Enforces the one rule that makes the public ingest endpoint safe: a
    client may only report kinds in
    :data:`~apps.security.constants.CLIENT_REPORTABLE`. Without it, any
    visitor could post ``scanner_agent`` events and have the platform
    auto-block whatever address they claimed to be.

    Args:
        kind: The reported :class:`SignalKind`.
        ip: Source address, taken from the connection — never the body.
        user_agent: Raw user agent.
        path: The frontend route the visitor was on.
        actor_id: Signed-in user, when there was one.
        request_id: Correlation id.
        detail: Client-supplied context, already validated and bounded.

    Returns:
        The recorded event, or ``None`` when nothing was recorded.

    Raises:
        SignalNotClientReportableError: If ``kind`` is server-only.
    """
    if kind not in CLIENT_REPORTABLE:
        raise SignalNotClientReportableError(
            f"'{kind}' cannot be reported by a client."
        )
    if not config.client_reports_enabled():
        return None
    return record(
        kind=kind,
        ip=ip,
        user_agent=user_agent,
        path=path,
        method="CLIENT",
        actor_id=actor_id,
        request_id=request_id,
        detail=detail,
    )


def record_edge_signal(
    *,
    secret: str,
    kind: str,
    ip: str,
    user_agent: str = "",
    path: str = "",
    request_id: str = "",
    detail: dict | None = None,
) -> SecurityEvent | None:
    """Record a signal the trusted frontend edge observed on our behalf.

    The Next.js origin serves the public site; requests for ``/.env``
    aimed at it never reach Django at all. This is the one path by which
    an address other than the caller's own may be recorded, so it is
    gated three ways: forwarding must be configured, the shared secret
    must match, and the kind must be edge-reportable.

    Args:
        secret: The secret the caller presented.
        kind: The reported :class:`SignalKind`.
        ip: The *visitor's* address, as seen by the edge.
        user_agent: The visitor's user agent.
        path: The path the visitor requested.
        request_id: Correlation id.
        detail: Detector context from the edge.

    Returns:
        The recorded event, or ``None`` when nothing was recorded.

    Raises:
        EdgeForwardingDisabledError: If no secret is configured.
        EdgeSecretMismatchError: If the presented secret is wrong.
        SignalNotEdgeReportableError: If ``kind`` is not edge-reportable.
    """
    expected = config.ingest_secret()
    if not expected:
        raise EdgeForwardingDisabledError()
    # Constant-time comparison: the secret is long-lived, and a timing
    # oracle on an endpoint anyone can reach would leak it byte by byte.
    if not compare_digest(secret, expected):
        raise EdgeSecretMismatchError()
    if kind not in EDGE_REPORTABLE:
        raise SignalNotEdgeReportableError(f"'{kind}' cannot be reported by the edge.")

    return record(
        kind=kind,
        ip=ip,
        user_agent=user_agent,
        path=path,
        method="EDGE",
        request_id=request_id,
        detail=detail,
    )


def is_blocked(profile: ThreatProfile, *, now: datetime | None = None) -> bool:
    """Whether a block is currently in force for this profile.

    Args:
        profile: The profile to test.
        now: Override for the current time.

    Returns:
        ``True`` while ``blocked_until`` lies in the future.
    """
    if profile.blocked_until is None:
        return False
    return profile.blocked_until > (now or timezone.now())


def _get_profile(profile_id: int) -> ThreatProfile:
    """Fetch a profile or raise the app's own 404.

    Args:
        profile_id: Primary key.

    Returns:
        The profile.

    Raises:
        ThreatProfileNotFoundError: If it does not exist.
    """
    profile = ThreatProfile.objects.filter(pk=profile_id).first()
    if profile is None:
        raise ThreatProfileNotFoundError()
    return profile


def block(*, profile_id: int, minutes: int, actor_id: int) -> ThreatProfile:
    """Block an address for a bounded window.

    Blocks are always time-boxed. A permanent block is a firewall rule
    an operator makes deliberately outside the application; letting the
    dashboard mint one invites a forgotten block that outlives everybody
    who remembers why it exists.

    Args:
        profile_id: Primary key of the profile.
        minutes: How long the block lasts.
        actor_id: The staff user issuing it.

    Returns:
        The updated profile.

    Raises:
        ThreatProfileNotFoundError: If the profile does not exist.
    """
    profile = _get_profile(profile_id)
    return threat_repository.set_block(
        profile=profile,
        until=timezone.now() + timedelta(minutes=minutes),
        actor_id=actor_id,
    )


def unblock(*, profile_id: int, actor_id: int) -> ThreatProfile:
    """Lift a block immediately.

    Args:
        profile_id: Primary key of the profile.
        actor_id: The staff user lifting it.

    Returns:
        The updated profile.

    Raises:
        ThreatProfileNotFoundError: If the profile does not exist.
    """
    profile = _get_profile(profile_id)
    return threat_repository.set_block(profile=profile, until=None, actor_id=actor_id)


def review(
    *, profile_id: int, state: str, actor_id: int, note: str = ""
) -> ThreatProfile:
    """Record a triage decision on a profile.

    Marking a profile reviewed changes **no** score and deletes **no**
    evidence — it only moves the row out of the operator's queue. If the
    address trips a detector again it returns to the queue by itself.

    Args:
        profile_id: Primary key of the profile.
        state: A :class:`ReviewState` value.
        actor_id: The staff user reviewing it.
        note: Optional reason.

    Returns:
        The updated profile.

    Raises:
        ThreatProfileNotFoundError: If the profile does not exist.
    """
    profile = _get_profile(profile_id)
    return threat_repository.set_review(
        profile=profile,
        state=ReviewState(state),
        reviewed_at=timezone.now(),
        actor_id=actor_id,
        note=note,
    )


__all__ = [
    "SignalKind",
    "block",
    "current_score",
    "decayed_score",
    "is_blocked",
    "record",
    "record_client_signal",
    "record_edge_signal",
    "review",
    "unblock",
]
