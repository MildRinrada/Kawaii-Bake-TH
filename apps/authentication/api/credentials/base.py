"""The credential seam.

Separates *who you are* (verified by the login service, request-free) from
*how the client proves it on later requests* (session cookie today, JWT later).

Everything request-bound about authentication lives behind this protocol.
``django.contrib.auth.login``/``logout`` and any future JWT library may be
imported **only** inside this package.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from apps.authentication.constants import STATUS_AUTHENTICATED

if TYPE_CHECKING:  # pragma: no cover - typing only
    from django.http import HttpRequest
    from rest_framework.response import Response

    from apps.users.models import User


@dataclass(frozen=True)
class IssuedCredential:
    """Everything the client needs after a successful authentication.

    Attributes:
        body: Extra keys merged into the JSON response. Empty for session
            cookies; ``{"access": "..."}`` for JWT.
        status: ``authenticated`` or ``mfa_required``. Shipping this field now
            means adding two-factor authentication later is an additive change
            rather than a breaking one.
    """

    body: dict[str, Any] = field(default_factory=dict)
    status: str = STATUS_AUTHENTICATED


class CredentialIssuer(Protocol):
    """Issues, revokes and refreshes the credential proving a session."""

    def issue(
        self, *, request: HttpRequest, user: User, remember: bool
    ) -> IssuedCredential:
        """Establish an authenticated session for ``user``."""
        ...

    def revoke(self, *, request: HttpRequest) -> None:
        """Terminate the caller's authenticated session."""
        ...

    def refresh(
        self, *, request: HttpRequest, payload: Mapping[str, Any]
    ) -> IssuedCredential:
        """Exchange a refresh credential for a new one."""
        ...

    def apply(self, *, response: Response, credential: IssuedCredential) -> None:
        """Attach transport-level artefacts (cookies, headers) to the response."""
        ...
