"""Runtime switches for threat watching, read from Django settings.

Every knob is an environment variable resolved in
``config/settings/base.py`` and read back through this module, so a
service never touches ``settings`` directly and a test can override one
switch with ``@override_settings`` without knowing the env var's name.

Reads go through ``getattr`` with the same default as ``base.py``: the
app must still import cleanly in a deployment whose settings file
predates these keys.
"""

from __future__ import annotations

from django.conf import settings

#: Client guard modes, weakest first.
GUARD_OFF = "off"
GUARD_DETECT = "detect"
GUARD_DETER = "deter"
GUARD_MODES = (GUARD_OFF, GUARD_DETECT, GUARD_DETER)


def watch_enabled() -> bool:
    """Whether the server-side detectors run at all."""
    return bool(getattr(settings, "SECURITY_WATCH_ENABLED", True))


def blocking_enabled() -> bool:
    """Whether ``blocked_until`` is enforced on incoming requests."""
    return bool(getattr(settings, "SECURITY_BLOCKING_ENABLED", True))


def auto_block_enabled() -> bool:
    """Whether reaching *critical* blocks an address without an operator.

    Off by default, and it should stay off until an operator has watched
    the dashboard for a while: an automatic block driven by heuristics is
    an automatic outage for whoever shares that address.
    """
    return bool(getattr(settings, "SECURITY_AUTO_BLOCK", False))


def auto_block_minutes() -> int:
    """How long an automatic block lasts."""
    return int(getattr(settings, "SECURITY_AUTO_BLOCK_MINUTES", 60))


def trusted_ips() -> frozenset[str]:
    """Addresses that are never scored and never blocked.

    The operator's own address belongs here. Without it, the first
    person to test the honeypot locks themselves out of the dashboard
    that would let them undo it.
    """
    return frozenset(getattr(settings, "SECURITY_TRUSTED_IPS", ()) or ())


def client_guard_mode() -> str:
    """The devtools-guard mode handed to the browser.

    ``off`` ships nothing. ``detect`` observes and reports. ``deter``
    also intercepts the devtools and view-source shortcuts. Unknown
    values fall back to ``off``  a typo in an env var must not turn a
    user-hostile mode on by accident.
    """
    mode = str(getattr(settings, "SECURITY_CLIENT_GUARD_MODE", GUARD_OFF)).lower()
    return mode if mode in GUARD_MODES else GUARD_OFF


def guard_exempts_authenticated() -> bool:
    """Whether signed-in visitors are left alone by the deterrent.

    Default on. The people most likely to open devtools on a learning
    platform are its own staff and its most engaged learners; blocking
    them buys nothing and costs trust.
    """
    return bool(getattr(settings, "SECURITY_GUARD_EXEMPT_AUTHENTICATED", True))


def client_reports_enabled() -> bool:
    """Whether the public client-signal ingest endpoint accepts posts."""
    return bool(getattr(settings, "SECURITY_CLIENT_REPORTS_ENABLED", True))


def ingest_secret() -> str:
    """Shared secret that lets a trusted edge forward a visitor's address.

    The Next.js origin sees trap requests the Django origin never does.
    When it forwards one, the client IP it reports is only believed if
    this secret matches  otherwise anyone could post events attributed
    to any address they liked. Empty (the default) disables forwarding.
    """
    return str(getattr(settings, "SECURITY_INGEST_SECRET", "") or "")
