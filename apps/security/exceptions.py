"""Domain errors raised by the security app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class ThreatProfileNotFoundError(DomainError):
    """Raised when an operator addresses a profile that does not exist."""

    code = "threat_profile_not_found"
    status_code = 404
    message = "Threat profile not found."


class SignalNotClientReportableError(DomainError):
    """Raised when a browser tries to report a server-only signal kind.

    A 400, not a 403: the request is malformed rather than unauthorised,
    and saying so does not tell an attacker which kinds *are* accepted
    beyond what the OpenAPI schema already publishes.
    """

    code = "signal_not_client_reportable"
    status_code = 400
    message = "This signal kind cannot be reported by a client."


class RequestBlockedError(DomainError):
    """Raised when a blocked address makes a request.

    Carries the standard envelope so a blocked client gets the same JSON
    shape as every other error  a bespoke response body would be one
    more thing for a scanner to fingerprint.
    """

    code = "request_blocked"
    status_code = 403
    message = "Request blocked by the security policy."


class EdgeForwardingDisabledError(DomainError):
    """Raised when the edge ingest is called with no secret configured.

    Answers 404 rather than 400 or 403: with forwarding switched off the
    endpoint does not meaningfully exist, and saying "wrong secret" to a
    deployment that has none would confirm the route to a scanner.
    """

    code = "not_found"
    status_code = 404
    message = "Not found."


class EdgeSecretMismatchError(DomainError):
    """Raised when the edge ingest is called with the wrong secret."""

    code = "edge_secret_invalid"
    status_code = 403
    message = "Edge ingest secret is not valid."


class SignalNotEdgeReportableError(DomainError):
    """Raised when the edge reports a kind it is not allowed to report."""

    code = "signal_not_edge_reportable"
    status_code = 400
    message = "This signal kind cannot be reported by the edge."
