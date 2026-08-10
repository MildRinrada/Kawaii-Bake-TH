"""Signal vocabulary, weights and level thresholds for threat watching.

Everything the scoring model needs is a constant in this module. That is
deliberate: an operator reading one file must be able to answer "why is
this IP marked *high*?" without tracing code, and a weight change is a
reviewable one-line diff rather than a behaviour buried in a service.
"""

from __future__ import annotations

from django.db import models


class SignalKind(models.TextChoices):
    """What was observed. Every value is produced by exactly one detector.

    The two families are scored very differently on purpose. *Server-side*
    kinds are observations the backend made itself and cannot be forged by
    the visitor. *Client-reported* kinds arrive from browser JavaScript,
    which any attacker can silence or spam — so they are worth a nudge,
    never a verdict (ADR 0025).
    """

    # --- server-observed ---------------------------------------------
    HONEYPOT_PATH = "honeypot_path", "Requested a trap path"
    SENSITIVE_FILE_PROBE = "sensitive_file_probe", "Probed for a secret file"
    PATH_TRAVERSAL = "path_traversal", "Path traversal attempt"
    SQLI_PROBE = "sqli_probe", "SQL injection probe"
    XSS_PROBE = "xss_probe", "Cross-site scripting probe"
    SCANNER_AGENT = "scanner_agent", "Known attack tool user agent"
    AUTOMATION_AGENT = "automation_agent", "Scripted client (curl, requests…)"
    MISSING_USER_AGENT = "missing_user_agent", "No user agent supplied"
    NOT_FOUND_SWEEP = "not_found_sweep", "Burst of 404s (content sweep)"
    AUTH_FAILURE_BURST = "auth_failure_burst", "Burst of rejected requests"
    REQUEST_FLOOD = "request_flood", "Request rate far above normal"

    # --- client-reported (advisory only) ------------------------------
    DEVTOOLS_OPENED = "devtools_opened", "Browser devtools appear to be open"
    VIEW_SOURCE_ATTEMPT = "view_source_attempt", "View-source shortcut pressed"
    CONTEXT_MENU_ATTEMPT = "context_menu_attempt", "Context menu suppressed"
    CONSOLE_TAMPER = "console_tamper", "Console/debugger tampering detected"


#: Kinds a browser is allowed to report. Anything else arriving at the
#: public ingest endpoint is rejected — a client must not be able to
#: manufacture a "scanner_agent" event against someone else's address.
CLIENT_REPORTABLE = frozenset(
    {
        SignalKind.DEVTOOLS_OPENED,
        SignalKind.VIEW_SOURCE_ATTEMPT,
        SignalKind.CONTEXT_MENU_ATTEMPT,
        SignalKind.CONSOLE_TAMPER,
    }
)


#: Kinds the *trusted edge* may report — the Next.js origin, proving
#: itself with `SECURITY_INGEST_SECRET`. It sees trap requests aimed at
#: the public site that never reach Django, so it may report the
#: server-observed kinds a browser may not. Windowed kinds stay out:
#: those are counted per-process and would double-count across origins.
EDGE_REPORTABLE = frozenset(
    {
        SignalKind.HONEYPOT_PATH,
        SignalKind.SENSITIVE_FILE_PROBE,
        SignalKind.PATH_TRAVERSAL,
        SignalKind.SQLI_PROBE,
        SignalKind.XSS_PROBE,
        SignalKind.SCANNER_AGENT,
        SignalKind.AUTOMATION_AGENT,
        SignalKind.MISSING_USER_AGENT,
    }
)


class ThreatLevel(models.TextChoices):
    """The four-band summary shown to operators."""

    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class ReviewState(models.TextChoices):
    """Where a profile sits in the operator's triage queue."""

    OPEN = "open", "Needs review"
    ACKNOWLEDGED = "acknowledged", "Reviewed — watching"
    IGNORED = "ignored", "Reviewed — benign"


#: Points a single observation adds to the offender's score.
#:
#: Calibrated so that one unambiguous attack signal alone reaches *high*,
#: two reach *critical*, while merely-suspicious behaviour has to repeat
#: several times before it outranks a single real probe. Client-reported
#: kinds sit at the bottom because they are advisory and forgeable.
SIGNAL_WEIGHTS: dict[str, int] = {
    SignalKind.SCANNER_AGENT: 60,
    SignalKind.SQLI_PROBE: 55,
    SignalKind.PATH_TRAVERSAL: 50,
    SignalKind.HONEYPOT_PATH: 45,
    SignalKind.SENSITIVE_FILE_PROBE: 40,
    SignalKind.XSS_PROBE: 35,
    SignalKind.AUTH_FAILURE_BURST: 25,
    SignalKind.NOT_FOUND_SWEEP: 20,
    SignalKind.REQUEST_FLOOD: 15,
    SignalKind.AUTOMATION_AGENT: 12,
    SignalKind.CONSOLE_TAMPER: 8,
    SignalKind.MISSING_USER_AGENT: 6,
    SignalKind.DEVTOOLS_OPENED: 4,
    SignalKind.VIEW_SOURCE_ATTEMPT: 3,
    SignalKind.CONTEXT_MENU_ATTEMPT: 1,
}

#: Lower bound of each band, highest first. Read top-down.
#:
#: The critical floor sits just *below* two honeypot hits (2 x 45) rather
#: than exactly on it. Decay is applied before every increment, so a score
#: that should land on a threshold lands a hair under it; a floor placed
#: on the nose would make the band flap on rounding.
LEVEL_THRESHOLDS: tuple[tuple[str, float], ...] = (
    (ThreatLevel.CRITICAL, 85.0),
    (ThreatLevel.HIGH, 45.0),
    (ThreatLevel.MEDIUM, 15.0),
    (ThreatLevel.LOW, 0.0),
)

#: A score halves after this many hours of silence. Old noise must not
#: keep an address flagged forever, and a genuine attacker re-earns the
#: points faster than they decay.
SCORE_HALF_LIFE_HOURS = 12.0

#: Ceiling on a stored score, so a sustained flood cannot make a profile
#: take weeks to decay back out of *critical*.
MAX_SCORE = 300.0

# --------------------------------------------------------------------------
# Detector inputs
# --------------------------------------------------------------------------

#: Paths that exist nowhere in this project. A request for one is not a
#: mistake a real visitor or a well-behaved crawler can make.
HONEYPOT_PATHS: tuple[str, ...] = (
    "/.env",
    "/.env.local",
    "/.env.production",
    "/.git/config",
    "/.git/head",
    "/.aws/credentials",
    "/.ssh/id_rsa",
    "/wp-login.php",
    "/wp-admin",
    "/wp-content",
    "/xmlrpc.php",
    "/phpmyadmin",
    "/phpinfo.php",
    "/shell.php",
    "/cgi-bin",
    "/vendor/phpunit",
    "/actuator/env",
    "/config.json",
    "/credentials.json",
    "/server-status",
)

#: Extensions that only ever appear in a backup or a leaked secret.
SENSITIVE_SUFFIXES: tuple[str, ...] = (
    ".sql",
    ".sql.gz",
    ".bak",
    ".backup",
    ".dump",
    ".pem",
    ".key",
    ".p12",
    ".sqlite3",
    ".db",
    ".zip",
    ".tar.gz",
    ".log",
)

#: Substrings that identify a security tool by name. These are advertised
#: by the tool itself, so a match is a strong signal and a miss means
#: nothing — the absence of evidence is not evidence of absence.
SCANNER_AGENT_MARKERS: tuple[str, ...] = (
    "sqlmap",
    "nikto",
    "nmap",
    "masscan",
    "zgrab",
    "nuclei",
    "acunetix",
    "wpscan",
    "dirbuster",
    "gobuster",
    "feroxbuster",
    "havij",
)

#: Ordinary scripting clients. Suspicious on a browser-facing site,
#: perfectly normal against an API — hence the low weight.
AUTOMATION_AGENT_MARKERS: tuple[str, ...] = (
    "curl/",
    "wget",
    "python-requests",
    "python-urllib",
    "httpie",
    "go-http-client",
    "java/",
    "okhttp",
    "libwww-perl",
    "scrapy",
    "axios/",
    "node-fetch",
    "guzzlehttp",
    "postmanruntime",
)

#: Crawlers that are allowed to crawl. Matched before the automation list
#: so a search engine indexing public recipes is never scored.
ALLOWED_CRAWLER_MARKERS: tuple[str, ...] = (
    "googlebot",
    "bingbot",
    "duckduckbot",
    "applebot",
    "slurp",
    "facebookexternalhit",
    "twitterbot",
    "linkedinbot",
    "line-poker",
    "telegrambot",
)

#: Query-string shapes that no legitimate form on this site produces.
SQLI_MARKERS: tuple[str, ...] = (
    "union select",
    "union all select",
    "' or '1'='1",
    '" or "1"="1',
    " or 1=1",
    "sleep(",
    "benchmark(",
    "information_schema",
    "load_file(",
    "pg_sleep",
    "waitfor delay",
    "--+",
    "/*!",
)

XSS_MARKERS: tuple[str, ...] = (
    "<script",
    "javascript:",
    "onerror=",
    "onload=",
    "document.cookie",
    "<iframe",
    "<svg/onload",
)

TRAVERSAL_MARKERS: tuple[str, ...] = (
    "../",
    "..\\",
    "%2e%2e",
    "..%2f",
    "/etc/passwd",
    "/proc/self/environ",
    "c:\\windows",
    "win.ini",
)

# --------------------------------------------------------------------------
# Sliding-window thresholds (counted in the cache, not the database)
# --------------------------------------------------------------------------

#: How many 404s from one address within the window count as a sweep.
NOT_FOUND_WINDOW_SECONDS = 60
NOT_FOUND_THRESHOLD = 12

#: How many 401/403 responses within the window count as a burst.
AUTH_FAILURE_WINDOW_SECONDS = 120
AUTH_FAILURE_THRESHOLD = 10

#: How many requests within the window count as a flood.
FLOOD_WINDOW_SECONDS = 10
FLOOD_THRESHOLD = 80

#: Field caps — these columns hold attacker-controlled text, so they are
#: bounded here and truncated on write rather than trusted.
PATH_MAX_LENGTH = 400
USER_AGENT_MAX_LENGTH = 400
NOTE_MAX_LENGTH = 300


def level_for_score(score: float) -> str:
    """Return the band a score falls into.

    Args:
        score: A non-negative threat score.

    Returns:
        A :class:`ThreatLevel` value.
    """
    for level, floor in LEVEL_THRESHOLDS:
        if score >= floor:
            return level
    return ThreatLevel.LOW
