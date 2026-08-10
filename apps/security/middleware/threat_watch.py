"""Request-path threat watching.

Two jobs, in this order:

1. **Enforce** an active block, before the view runs.
2. **Observe** — inspect the request, and after the response, look at
   rate-shaped behaviour that no single request reveals.

Both are wrapped so that a failure here degrades to "not watching" rather
than "site down". A monitoring feature that can take the platform offline
is a bigger availability risk than the scanners it watches for.

Cost control: the detectors are pure string work on every request, but a
**database write happens only when a rule actually fires**. Normal
traffic costs one dict lookup and a few substring scans, plus one cached
counter increment. The block check reads a short-lived cached set rather
than the table.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.common.api.views import client_ip
from apps.security import blocklist, config
from apps.security.constants import (
    AUTH_FAILURE_THRESHOLD,
    AUTH_FAILURE_WINDOW_SECONDS,
    FLOOD_THRESHOLD,
    FLOOD_WINDOW_SECONDS,
    NOT_FOUND_THRESHOLD,
    NOT_FOUND_WINDOW_SECONDS,
    SignalKind,
)
from apps.security.detectors import request_rules
from apps.security.exceptions import RequestBlockedError
from apps.security.services import threat_service

logger = logging.getLogger("kawaiibake.security")

#: One profile only re-earns a windowed signal once per window, so a
#: 200-request flood produces one flood event, not two hundred.
_WINDOW_KEYS = {
    SignalKind.NOT_FOUND_SWEEP: ("security:404:{ip}", NOT_FOUND_WINDOW_SECONDS),
    SignalKind.AUTH_FAILURE_BURST: (
        "security:authfail:{ip}",
        AUTH_FAILURE_WINDOW_SECONDS,
    ),
    SignalKind.REQUEST_FLOOD: ("security:rate:{ip}", FLOOD_WINDOW_SECONDS),
}


def _bump(kind: str, ip: str) -> bool:
    """Increment a sliding-window counter and report whether it just tripped.

    Returns ``True`` exactly once per window — on the request that
    crosses the threshold — so a sustained burst is one event, not one
    per request over the line.

    Args:
        kind: The windowed :class:`SignalKind`.
        ip: Source address.

    Returns:
        ``True`` when this call crossed the threshold.
    """
    template, window = _WINDOW_KEYS[kind]
    thresholds = {
        SignalKind.NOT_FOUND_SWEEP: NOT_FOUND_THRESHOLD,
        SignalKind.AUTH_FAILURE_BURST: AUTH_FAILURE_THRESHOLD,
        SignalKind.REQUEST_FLOOD: FLOOD_THRESHOLD,
    }
    key = template.format(ip=ip)
    cache.add(key, 0, window)
    try:
        count = cache.incr(key)
    except ValueError:
        # The key expired between `add` and `incr`; the next request in
        # the new window counts it. Losing one tick is fine, raising is not.
        return False
    return count == thresholds[kind]


class ThreatWatchMiddleware:
    """Observe every request; enforce blocks; never break serving."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Store the next handler in the middleware chain."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Run the watcher around the rest of the chain."""
        if not config.watch_enabled():
            return self.get_response(request)

        ip = client_ip(request)
        trusted = (not ip) or ip in config.trusted_ips()

        if not trusted and config.blocking_enabled() and ip in blocklist.blocked_ips():
            return self._blocked_response(request)

        if not trusted:
            self._safely(self._inspect, request, ip)

        response = self.get_response(request)

        if not trusted:
            self._safely(self._observe_response, request, ip, response)
        return response

    # -- internals ----------------------------------------------------

    def _safely(self, func: Callable, *args: object) -> None:
        """Run a watcher step, swallowing and logging any failure."""
        try:
            func(*args)
        except Exception:  # noqa: BLE001 — watching must never break serving
            logger.exception("security: watcher step failed")

    def _blocked_response(self, request: HttpRequest) -> JsonResponse:
        """Return the standard error envelope with a 403."""
        error = RequestBlockedError()
        return JsonResponse(
            {
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "details": {},
                    "request_id": getattr(request, "request_id", ""),
                }
            },
            status=error.status_code,
        )

    def _inspect(self, request: HttpRequest, ip: str) -> None:
        """Score anything the pure detectors recognise in this request."""
        signal = request_rules.inspect_request(
            path=request.path,
            query=request.META.get("QUERY_STRING", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        if signal is None:
            return
        threat_service.record(
            kind=signal.kind,
            ip=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            path=request.path,
            method=request.method or "",
            actor_id=self._actor_id(request),
            request_id=getattr(request, "request_id", ""),
            detail=dict(signal.detail),
        )

    def _observe_response(
        self, request: HttpRequest, ip: str, response: HttpResponse
    ) -> None:
        """Score rate-shaped behaviour that one request cannot show."""
        windowed: str | None = None
        if _bump(SignalKind.REQUEST_FLOOD, ip):
            windowed = SignalKind.REQUEST_FLOOD
        if response.status_code == 404 and _bump(SignalKind.NOT_FOUND_SWEEP, ip):
            windowed = SignalKind.NOT_FOUND_SWEEP
        if response.status_code in (401, 403) and _bump(
            SignalKind.AUTH_FAILURE_BURST, ip
        ):
            windowed = SignalKind.AUTH_FAILURE_BURST
        if windowed is None:
            return
        threat_service.record(
            kind=windowed,
            ip=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            path=request.path,
            method=request.method or "",
            status_code=response.status_code,
            actor_id=self._actor_id(request),
            request_id=getattr(request, "request_id", ""),
        )

    @staticmethod
    def _actor_id(request: HttpRequest) -> int | None:
        """The signed-in user's id, if the auth middleware has run."""
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return user.id
        return None
