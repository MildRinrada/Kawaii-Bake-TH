"""Pure request inspection: (path, query, user agent) → signal or nothing.

Deliberately framework-free  no ``HttpRequest``, no ORM, no settings.
Detection rules are the part of this app most likely to be wrong, so they
are written as functions over strings that a test can call directly with
a hostile input and no database.

Each rule returns at most one :class:`Signal`; :func:`inspect_request`
returns the single **worst** match rather than every match. One request
is one observation: scoring a single hostile URL five times would let the
band say "critical" on the strength of one packet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import unquote_plus

from apps.security.constants import (
    ALLOWED_CRAWLER_MARKERS,
    AUTOMATION_AGENT_MARKERS,
    HONEYPOT_PATHS,
    SCANNER_AGENT_MARKERS,
    SENSITIVE_SUFFIXES,
    SIGNAL_WEIGHTS,
    SQLI_MARKERS,
    TRAVERSAL_MARKERS,
    XSS_MARKERS,
    SignalKind,
)


@dataclass(frozen=True)
class Signal:
    """One detector's verdict about one request."""

    kind: str
    detail: dict[str, str] = field(default_factory=dict)

    @property
    def weight(self) -> int:
        """Points this signal contributes."""
        return SIGNAL_WEIGHTS[self.kind]


def _decode(value: str) -> str:
    """Lower-case and percent-decode once, for marker matching.

    A single decode pass is intentional. Decoding repeatedly until the
    string stops changing is how scanners get a rule to "find" an attack
    in a legitimate URL that merely contains an encoded percent sign.

    Args:
        value: Raw path or query string.

    Returns:
        The normalised form used by every marker test.
    """
    return unquote_plus(value).lower()


def check_user_agent(user_agent: str) -> Signal | None:
    """Classify the client that sent the request.

    Order matters: a permitted crawler is cleared before the automation
    list can match it, and a named attack tool outranks both.

    Args:
        user_agent: The raw ``User-Agent`` header, possibly empty.

    Returns:
        The matching signal, or ``None`` for an ordinary browser.
    """
    agent = user_agent.strip().lower()
    if not agent:
        return Signal(SignalKind.MISSING_USER_AGENT)

    for marker in SCANNER_AGENT_MARKERS:
        if marker in agent:
            return Signal(SignalKind.SCANNER_AGENT, {"marker": marker})

    # Search engines and social unfurlers are supposed to be here.
    if any(marker in agent for marker in ALLOWED_CRAWLER_MARKERS):
        return None

    for marker in AUTOMATION_AGENT_MARKERS:
        if marker in agent:
            return Signal(SignalKind.AUTOMATION_AGENT, {"marker": marker})

    return None


def check_path(path: str) -> Signal | None:
    """Look for trap paths, secret-file probes and traversal.

    Args:
        path: The request path, without the query string.

    Returns:
        The matching signal, or ``None``.
    """
    decoded = _decode(path)

    for marker in TRAVERSAL_MARKERS:
        if marker in decoded:
            return Signal(SignalKind.PATH_TRAVERSAL, {"marker": marker})

    for trap in HONEYPOT_PATHS:
        # Prefix, not equality: `/wp-admin/setup-config.php` is the same
        # scan as `/wp-admin`, and equality would miss every variation.
        if decoded == trap or decoded.startswith(f"{trap}/"):
            return Signal(SignalKind.HONEYPOT_PATH, {"trap": trap})

    for suffix in SENSITIVE_SUFFIXES:
        if decoded.endswith(suffix):
            return Signal(SignalKind.SENSITIVE_FILE_PROBE, {"suffix": suffix})

    return None


def check_query(query: str) -> Signal | None:
    """Look for injection payloads in the query string.

    Args:
        query: The raw query string, without the leading ``?``.

    Returns:
        The matching signal, or ``None``.
    """
    if not query:
        return None
    decoded = _decode(query)

    for marker in SQLI_MARKERS:
        if marker in decoded:
            return Signal(SignalKind.SQLI_PROBE, {"marker": marker})

    for marker in XSS_MARKERS:
        if marker in decoded:
            return Signal(SignalKind.XSS_PROBE, {"marker": marker})

    for marker in TRAVERSAL_MARKERS:
        if marker in decoded:
            return Signal(SignalKind.PATH_TRAVERSAL, {"marker": marker})

    return None


def inspect_request(
    *, path: str, query: str = "", user_agent: str = ""
) -> Signal | None:
    """Run every rule and return the single most severe match.

    Args:
        path: Request path without the query string.
        query: Raw query string.
        user_agent: Raw ``User-Agent`` header.

    Returns:
        The worst signal found, or ``None`` when the request looks ordinary.
    """
    candidates = [
        signal
        for signal in (
            check_path(path),
            check_query(query),
            check_user_agent(user_agent),
        )
        if signal is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda signal: signal.weight)
